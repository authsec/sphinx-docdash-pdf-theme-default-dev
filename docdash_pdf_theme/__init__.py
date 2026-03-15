import os
import re
from pathlib import Path
from datetime import datetime
from sphinx.util import logging
from jinja2 import Environment
from sphinx.writers.latex import LaTeXTranslator
from docutils import nodes
from docutils.parsers.rst import Directive, directives

logger = logging.getLogger(__name__)

__version__ = "0.1.117"

def get_safe_filename(name: str) -> str:
    """Creates a filesystem-safe string from a project name."""
    safe = re.sub(r'[^A-Za-z0-9\s]+', '', name).strip().replace(' ', '_')
    return safe.lower() or "document"

def adjust_hex_brightness(hex_color: str, percentage: float) -> str:
    """
    Adjusts the brightness of a hex color.
    
    :param hex_color: The original hex color string (e.g., '#ADAEDD' or '#ADAEDD80').
    :param percentage: Float from -100.0 to 100.0. Positive values lighten, negative values darken.
    :return: A new hex color string, preserving alpha if present (e.g., '#CBE1FF' or '#CBE1FF80').
    """
    if not hex_color:
        return None
        
    hex_color = hex_color.lstrip('#')
    has_alpha = False
    alpha_str = ""
    
    # Support 4-char shorthand (RGBA)
    if len(hex_color) == 4:
        hex_color = ''.join([c*2 for c in hex_color])
        
    # Support 3-char shorthand (RGB)
    elif len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])

    # Extract and preserve alpha channel
    if len(hex_color) == 8:
        has_alpha = True
        alpha_str = hex_color[6:8]
        hex_color = hex_color[:6]
        
    if len(hex_color) != 6:
        logger.warning(f"[DocDash] Invalid hex color '#{hex_color}'. Cannot adjust brightness.")
        return f"#{hex_color}{alpha_str}"

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    factor = percentage / 100.0

    if factor > 0:
        # Lighten towards white
        r = r + (255 - r) * factor
        g = g + (255 - g) * factor
        b = b + (255 - b) * factor
    elif factor < 0:
        # Darken towards black
        r = r * (1 + factor)
        g = g * (1 + factor)
        b = b * (1 + factor)

    # Clamp the values between 0 and 255 and format back to Hex
    r = max(0, min(255, int(round(r))))
    g = max(0, min(255, int(round(g))))
    b = max(0, min(255, int(round(b))))

    if has_alpha:
        return f"#{r:02X}{g:02X}{b:02X}{alpha_str}"
    return f"#{r:02X}{g:02X}{b:02X}"


def _hex_to_rgb(hex_color: str):
    """Helper to safely extract 8-bit RGB values from a hex string."""
    clean = hex_color.lstrip('#')
    if len(clean) == 8:
        clean = clean[:6]
    elif len(clean) == 4:
        clean = ''.join([c*2 for c in clean[:3]])
    elif len(clean) == 3:
        clean = ''.join([c*2 for c in clean])
    if len(clean) != 6:
        return 0, 0, 0
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)

def _get_luminance(hex_color: str) -> float:
    """Calculates relative luminance according to WCAG 2.0 standards."""
    r, g, b = _hex_to_rgb(hex_color)
    srgb = [x / 255.0 for x in (r, g, b)]
    linear = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

def _get_contrast_ratio(lum1: float, lum2: float) -> float:
    """Calculates the contrast ratio between two relative luminance values."""
    l1 = max(lum1, lum2)
    l2 = min(lum1, lum2)
    return (l1 + 0.05) / (l2 + 0.05)

def get_highest_contrast_color(foreground_color: str, background_color: str, target: str = 'foreground', adjust_percent: float = 0.0) -> str:
    """
    Modifies the target color to ensure a WCAG 2.0 contrast ratio of at least 4.5:1.
    
    :param foreground_color: Hex color string (e.g., text color).
    :param background_color: Hex color string (e.g., background color).
    :param target: 'foreground' or 'background' (which color should be shifted to reach compliance).
    :param adjust_percent: Additional percentage to lighten/darken the final valid output.
    :return: A WCAG compliant hex color string, preserving alpha.
    """
    if not foreground_color or not background_color:
        return None
        
    if target == 'foreground':
        target_color = foreground_color
        fixed_color = background_color
    else:
        target_color = background_color
        fixed_color = foreground_color
        
    lum_fixed = _get_luminance(fixed_color)
    lum_target = _get_luminance(target_color)
    
    candidate = target_color
    
    if _get_contrast_ratio(lum_fixed, lum_target) < 4.5:
        # 0.17912 is the exact luminance where black and white offer identical contrast (4.58)
        direction = -1 if lum_fixed > 0.17912 else 1
        
        # Iteratively shift the target color towards black/white until it hits the 4.5 threshold
        for i in range(1, 101):
            test_color = adjust_hex_brightness(target_color, i * direction)
            if _get_contrast_ratio(lum_fixed, _get_luminance(test_color)) >= 4.5:
                candidate = test_color
                break
        else:
            # Fallback to pure black/white if loop is exhausted
            clean = target_color.lstrip('#')
            base = "#000000" if direction == -1 else "#FFFFFF"
            
            if len(clean) == 8:
                candidate = base + clean[6:8]
            elif len(clean) == 4:
                candidate = base + (clean[3]*2)
            else:
                candidate = base
                
    if adjust_percent != 0.0:
        return adjust_hex_brightness(candidate, adjust_percent)
        
    return candidate


def hex_to_cmyk_string(hex_color: str) -> str:
    """Converts a hex color string (e.g., '#FF0000') to a LaTeX CMYK string."""
    if not hex_color:
        return None
        
    hex_color = hex_color.lstrip('#')
    
    # Support 8-char (RGBA) by dropping alpha, and 3-char shorthand
    if len(hex_color) == 8:
        hex_color = hex_color[:6]
    elif len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
        
    if len(hex_color) != 6:
        logger.warning(f"[DocDash] Invalid hex color '#{hex_color}'. Falling back to black.")
        return "0, 0, 0, 1"

    # Convert Hex to RGB [0.0 - 1.0]
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    # Calculate CMYK
    k = 1.0 - max(r, g, b)
    if k == 1.0:
        return "0, 0, 0, 1"
    
    c = (1.0 - r - k) / (1.0 - k)
    m = (1.0 - g - k) / (1.0 - k)
    y = (1.0 - b - k) / (1.0 - k)

    return f"{c:.3f}, {m:.3f}, {y:.3f}, {k:.3f}"

class StyleBoxDirective(Directive):
    """Custom directive to safely parse container styles and preserve capitalized titles."""
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {
        'name': directives.unchanged,
        'title': directives.unchanged,
        'class': directives.class_option
    }
    has_content = True

    def run(self):
        self.assert_has_content()
        container = nodes.container()
        
        # First argument is now the class(es), just like standard .. container::
        if self.arguments:
            container['classes'].extend(self.arguments[0].split())
            
        # Allow fallback to standard :class: just in case
        container['classes'].extend(self.options.get('class', []))

        # Retrieve un-mutated title string from either :title: or :name:
        raw_title = self.options.get('title') or self.options.get('name')
        if raw_title:
            container['docdash_stylebox_title'] = raw_title

        # Apply standard docutils name normalization for HTML/Sphinx cross-referencing
        self.add_name(container)

        self.state.nested_parse(self.content, self.content_offset, container)
        return [container]

def process_containers_ast(app, doctree, docname):
    """Safely extracts container classes and wraps them in custom LaTeX tcolorboxes."""
    if getattr(app.builder, 'format', '') != 'latex':
        return

    containers_conf = getattr(app.config, 'docdash_containers', {})
    if not containers_conf:
        return

    for node in list(doctree.traverse(nodes.container)):
        if node.get('docdash_processed'):
            continue

        match_class = None
        for c in node.get('classes', []):
            if c in containers_conf:
                match_class = c
                break

        if not match_class:
            continue

        node['docdash_processed'] = True

        # Extract title preferentially from our robust custom directive
        title = node.get('docdash_stylebox_title', None)
        
        # Fallback to the lowercased :name: option if they used standard containers
        if title is None:
            names = node.get('names', [])
            title = names[0] if names else ""

        def esc(s):
            if not s: return ''
            return str(s).replace('_', r'\_').replace('%', r'\%').replace('$', r'\$').replace('#', r'\#').replace('&', r'\&').replace('{', r'\{').replace('}', r'\}').replace('\n', ' ').replace('\r', '').strip()

        safe_title = esc(title)
        
        # Sanitize the class name to prevent LaTeX pgfkeys crash
        safe_match_class = re.sub(r'[^a-zA-Z]', '', match_class)

        # Conditionally apply the complex title styles only if a title actually exists
        if safe_title:
            icon_tex = f"\\csname ddconticon{safe_match_class}\\endcsname"
            title_str = f"ddcontainertitlestyle{safe_match_class}, title={{{icon_tex} {safe_title}}}"
        else:
            title_str = "notitle"

        wrapper = nodes.container(classes=['docdash-flat-container'])
        wrapper.append(nodes.raw('', f'\n\\begin{{ddcontainer{safe_match_class}}}[{title_str}]\n', format='latex'))
        wrapper.extend(node.children)
        wrapper.append(nodes.raw('', f'\n\\end{{ddcontainer{safe_match_class}}}\n', format='latex'))

        node.replace_self(wrapper)

def config_inited(app, config):
    """Fired when Sphinx finishes reading conf.py."""
    
    # 1. Smart default for latex_engine
    if config.latex_engine == 'pdflatex':
        config.latex_engine = 'lualatex'
    elif config.latex_engine != 'lualatex':
        logger.warning(
            f"[DocDash PDF Theme] The latex_engine is set to '{config.latex_engine}'. "
            "This theme is designed for 'lualatex'. Your build might not render correctly."
        )

    # 2. Set default document class to KOMA (scrbook)
    if not config.latex_docclass:
         config.latex_docclass = {'manual': 'scrbook'}
    else:
         config.latex_docclass.setdefault('manual', 'scrbook')

    # 3. Dynamic LaTeX document naming
    safe_project = get_safe_filename(config.project)
    if not config.latex_documents or 'outpdfname.tex' in config.latex_documents[0][1]:
        config.latex_documents = [
            (config.root_doc, f"{safe_project}.tex", config.project, config.author, 'manual'),
        ]

    # 4. Render Preamble Template with Custom Colors
    pkg_dir = Path(__file__).parent.resolve()
    preamble_path = pkg_dir / "preamble.tex_t"
    
    if preamble_path.exists():
        template_content = preamble_path.read_text(encoding="utf-8")
        
        # Configure Jinja with LaTeX-safe delimiters to prevent '{%' clashes
        env = Environment(
            block_start_string='<%',
            block_end_string='%>',
            variable_start_string='<<',
            variable_end_string='>>',
            comment_start_string='<#',
            comment_end_string='#>'
        )
        template = env.from_string(template_content)
        
        template_vars = {
            'docdash_subtitle': getattr(config, 'docdash_subtitle', None),
            'docdash_show_release': getattr(config, 'docdash_show_release', True),
            'docdash_title_page_color': hex_to_cmyk_string(getattr(config, 'docdash_title_page_color', None)),
            'docdash_title_page_top_line': getattr(config, 'docdash_title_page_top_line', False),
            'docdash_headsep': getattr(config, 'docdash_headsep', '8mm'),
            'docdash_footskip': getattr(config, 'docdash_footskip', '10mm'),
            'docdash_headheight': getattr(config, 'docdash_headheight', '18pt'),
            'docdash_footheight': getattr(config, 'docdash_footheight', '25pt'),
            'extensions': getattr(config, 'extensions', [])
        }

        # --- CONTAINER CUSTOMIZATION LOGIC ---
        containers = getattr(config, 'docdash_containers', {})
        safe_containers = {}
        for c_name, c_conf in containers.items():
            # Sanitize the class name for LaTeX variables
            safe_name = re.sub(r'[^a-zA-Z]', '', c_name)
            
            title_color = c_conf.get('title_color', '#000000')
            c_conf['title_color_cmyk'] = hex_to_cmyk_string(title_color)
            c_conf['title_font_color_cmyk'] = hex_to_cmyk_string(c_conf.get('title_font_color', get_highest_contrast_color(title_color, title_color, target='foreground')))
            c_conf['content_font_color_cmyk'] = hex_to_cmyk_string(c_conf.get('content_font_color', '#000000'))
            c_conf['content_background_color_cmyk'] = hex_to_cmyk_string(c_conf.get('content_background_color', '#FFFFFF'))
            c_conf.setdefault('title_font_size', r'\large\bfseries')
            c_conf.setdefault('content_font_size', r'\normalsize')
            c_conf.setdefault('title_style', 'classic')
            
            # Prevent string conversion bugs (e.g. "False" instead of False)
            frame_val = c_conf.get('container_frame', True)
            if isinstance(frame_val, str):
                frame_val = frame_val.lower() not in ['false', '0', 'none', 'no']
            c_conf['container_frame'] = frame_val
            
            c_conf.setdefault('title_icon', '')
            c_conf.setdefault('title_font', '')
            c_conf.setdefault('content_font', '')
            
            safe_containers[safe_name] = c_conf
            
        template_vars['docdash_containers'] = safe_containers

        # --- DRAFT TEXT LOGIC ---
        draft_text = getattr(config, 'docdash_draft_text', None)
        if draft_text:
            date_fmt = getattr(config, 'docdash_draft_date_format', '%Y-%m-%d %H:%M:%S')
            formatted_date = datetime.now().strftime(date_fmt)
            ext_version = __version__
            proj_version = getattr(config, 'version', getattr(config, 'release', ''))
            
            draft_text = draft_text.replace('{date}', formatted_date)
            draft_text = draft_text.replace('{ext_version}', ext_version)
            draft_text = draft_text.replace('{project_version}', proj_version)
            template_vars['docdash_draft_text'] = draft_text
            
            draft_color_str = getattr(config, 'docdash_draft_color', '#00000044')
            draft_opacity = "1.0"
            if draft_color_str:
                clean_hex = draft_color_str.lstrip('#')
                if len(clean_hex) == 8:
                    draft_opacity = str(round(int(clean_hex[6:8], 16) / 255.0, 2))
                    draft_color_str = f"#{clean_hex[:6]}"
                elif len(clean_hex) == 4:
                    draft_opacity = str(round(int(clean_hex[3] * 2, 16) / 255.0, 2))
                    draft_color_str = f"#{clean_hex[:3]}"
                template_vars['docdash_draft_color_cmyk'] = hex_to_cmyk_string(draft_color_str)
                template_vars['docdash_draft_opacity'] = draft_opacity

            template_vars['docdash_draft_font'] = getattr(config, 'docdash_draft_font', None)
            template_vars['docdash_draft_font_size'] = getattr(config, 'docdash_draft_font_size', r'\Huge\bfseries\sffamily')
        else:
            template_vars['docdash_draft_text'] = None

        # --- PART BACKGROUNDS LOGIC ---
        part_bgs = getattr(config, 'docdash_part_backgrounds', {})
        processed_part_bgs = {}
        if getattr(config, 'latex_toplevel_sectioning', '') == 'part':
            for p_num, p_conf in part_bgs.items():
                try:
                    p_num_int = int(p_num)
                except ValueError:
                    continue
                
                img = p_conf.get('image', None)
                if img:
                    if img not in config.latex_additional_files:
                        config.latex_additional_files.append(img)
                    img = os.path.basename(img)
                
                color_str = p_conf.get('color', None)
                cmyk = None
                opacity = "1.0"
                if color_str:
                    clean_hex = color_str.lstrip('#')
                    if len(clean_hex) == 8:
                        opacity = str(round(int(clean_hex[6:8], 16) / 255.0, 2))
                        color_str = f"#{clean_hex[:6]}"
                    elif len(clean_hex) == 4:
                        opacity = str(round(int(clean_hex[3] * 2, 16) / 255.0, 2))
                        color_str = f"#{clean_hex[:3]}"
                    cmyk = hex_to_cmyk_string(color_str)
                    
                processed_part_bgs[p_num_int] = {
                    'image': img,
                    'color_cmyk': cmyk,
                    'opacity': opacity
                }
        template_vars['docdash_part_backgrounds'] = processed_part_bgs

        # Title Page Background Image Resolution
        title_bg = getattr(config, 'docdash_title_page_background_image', None)
        if title_bg and isinstance(title_bg, str):
            if title_bg not in config.latex_additional_files:
                config.latex_additional_files.append(title_bg)
            template_vars['docdash_title_page_background_image'] = os.path.basename(title_bg)
        else:
            template_vars['docdash_title_page_background_image'] = None

        # Title Page Tint Opacity
        opacity = getattr(config, 'docdash_title_page_color_opacity', None)
        if opacity is None:
            # Default to 50% opacity if there is an image, otherwise fully opaque
            opacity = '0.5' if template_vars['docdash_title_page_background_image'] else '1.0'
        template_vars['docdash_title_page_color_opacity'] = opacity

        # Footer Logo Resolution
        footer_logo = getattr(config, 'docdash_footer_logo', None)
        if footer_logo and isinstance(footer_logo, str):
            if footer_logo not in config.latex_additional_files:
                config.latex_additional_files.append(footer_logo)
            template_vars['docdash_footer_logo'] = os.path.basename(footer_logo)
        else:
            template_vars['docdash_footer_logo'] = None
            
        template_vars['docdash_footer_logo_height'] = getattr(config, 'docdash_footer_logo_height', '1.5em')
        
        # --- HEADING ALIGNMENT & MARGIN RESOLUTION ---
        global_align = getattr(config, 'docdash_heading_align', 'alternate')
        if global_align not in ['left', 'right', 'alternate']:
            global_align = 'alternate'
            
        for el in ['chapter', 'section', 'subsection', 'subsubsection']:
            val = getattr(config, f'docdash_{el}_align', None)
            if val not in ['left', 'right', 'alternate']:
                val = global_align
            template_vars[f'docdash_{el}_align'] = val

        global_margin = getattr(config, 'docdash_numbers_in_margin', True)
        global_margin_space = getattr(config, 'docdash_heading_margin_space', None) or '1.5em'
        
        for el in ['chapter', 'section', 'subsection', 'subsubsection']:
            margin_val = getattr(config, f'docdash_{el}_number_margin', None)
            template_vars[f'docdash_{el}_number_margin'] = margin_val if margin_val is not None else global_margin
            
            line_val = getattr(config, f'docdash_{el}_number_line', None)
            default_line = True if el == 'chapter' else False
            template_vars[f'docdash_{el}_number_line'] = line_val if line_val is not None else default_line
            
            height_val = getattr(config, f'docdash_{el}_line_height', None)
            template_vars[f'docdash_{el}_line_height'] = height_val if height_val else '10cm'
            
            space_val = getattr(config, f'docdash_{el}_margin_space', None)
            template_vars[f'docdash_{el}_margin_space'] = space_val if space_val else global_margin_space

        # --- TEXT INHERITANCE LOGIC ---
        elements = [
            'title', 'subtitle', 'author', 'date', 'release_version', 
            'part', 'chapter', 'section', 'subsection', 'subsubsection', 'rubric',
            'part_number', 'part_number_part', 'part_number_number', 
            'chapter_number', 'section_number', 'subsection_number', 'subsubsection_number',
            'chapter_line', 'section_line', 'subsection_line', 'subsubsection_line'
        ]
        for el in elements:
            template_vars[f'docdash_{el}_font'] = getattr(config, f'docdash_{el}_font', None)
            template_vars[f'docdash_{el}_size'] = getattr(config, f'docdash_{el}_size', None)
            template_vars[f'docdash_{el}_color'] = hex_to_cmyk_string(getattr(config, f'docdash_{el}_color', None))

        if getattr(config, 'docdash_inherit_all', True):
            hierarchies = [
                ['part', 'chapter', 'section', 'subsection', 'subsubsection'],
                ['part_number', 'chapter_number', 'section_number', 'subsection_number', 'subsubsection_number'],
                ['chapter_line', 'section_line', 'subsection_line', 'subsubsection_line']
            ]
            properties = [
                ('font', getattr(config, 'docdash_inherit_font', True)),
                ('color', getattr(config, 'docdash_inherit_color', True)),
                ('size', getattr(config, 'docdash_inherit_size', False))
            ]
            for hierarchy in hierarchies:
                for prop, is_enabled in properties:
                    if is_enabled:
                        current_val = template_vars[f'docdash_{hierarchy[0]}_{prop}']
                        for i in range(1, len(hierarchy)):
                            level = hierarchy[i]
                            key = f'docdash_{level}_{prop}'
                            if not template_vars[key]:
                                template_vars[key] = current_val
                            else:
                                current_val = template_vars[key]

        for prop in ['font', 'color', 'size']:
            if not template_vars[f'docdash_part_number_part_{prop}']:
                template_vars[f'docdash_part_number_part_{prop}'] = template_vars[f'docdash_part_number_{prop}']
            if not template_vars[f'docdash_part_number_number_{prop}']:
                template_vars[f'docdash_part_number_number_{prop}'] = template_vars[f'docdash_part_number_{prop}']

        # --- ADMONITION LOGIC ---
        generic_defaults = {
            'title_icon': r'\textbf{i}',
            'title_icon_color': '#FFFFFF',
            'title_icon_size': '',
            'title_icon_padding': '3ex',
            'title_decoration_spacing': '2mm',
            'title_font': '',
            'title_font_color': '#FFFFFF',
            'title_font_size': r'\large\bfseries',
            'title_background_color': '#0092FA',
            'title_icon_box_background_color': '#0092FA', 
            'content_background_color': '#F8F9FA',
            'content_background_color_nested': '#FFFFFF', 
            'content_font': '',
            'content_font_color': '#000000',
            'content_font_size': r'\normalsize',
            'before_skip': '2.2em plus 0.5em minus 0.5em',
            'after_skip': '1.5em plus 0.5em minus 0.5em'
        }

        admon_types = ['generic', 'admonition', 'note', 'warning', 'hint', 'danger', 'error', 'caution', 'tip', 'important', 'attention']
        admon_props = [
            'title_icon', 'title_icon_color', 'title_icon_size', 'title_icon_padding', 'title_decoration_spacing', 
            'title_font', 'title_font_color', 'title_font_size', 
            'title_background_color', 'title_icon_box_background_color', 
            'content_background_color', 'content_background_color_nested', 
            'content_font', 'content_font_color', 'content_font_size',
            'before_skip', 'after_skip'
        ]

        for t in admon_types:
            for p in admon_props:
                val = getattr(config, f'docdash_admonition_{t}_{p}', None)
                
                # Resolve Fallbacks
                if val is None:
                    if t == 'generic':
                        val = generic_defaults[p]
                    else:
                        val = template_vars[f'docdash_admonition_generic_{p}']
                
                # Image Path Icon Detection
                if p == 'title_icon' and val and not val.strip().startswith('\\') and not val.strip().startswith('<'):
                    if val not in config.latex_additional_files:
                        config.latex_additional_files.append(val)
                    base_filename = os.path.basename(val)
                    val = f"\\includegraphics[height=1em, keepaspectratio]{{{base_filename}}}"

                template_vars[f'docdash_admonition_{t}_{p}'] = val
                
                # Pre-calculate CMYK for colors
                if p.endswith('_color') or p.endswith('_nested'):
                    template_vars[f'docdash_admonition_{t}_{p}_cmyk'] = hex_to_cmyk_string(val)

        # --- SPHINX NEEDS LOGIC ---
        if 'sphinx_needs' in getattr(config, 'extensions', []):
            needs_props = [
                'title_font', 'title_font_size', 'title_color', 'title_background_color',
                'title_icon', 'title_icon_size', 'title_icon_color', 'title_icon_raise', 'title_icon_raise_offset', 'title_vertical_position',
                'metadata_background_color', 'metadata_font', 'metadata_font_size', 'metadata_font_color',
                'metadata_key_font', 'metadata_key_color', 'metadata_key_font_size',
                'content_background_color', 'content_font', 'content_font_size', 'content_font_color',
                'segmentation_style', 'segmentation_color',
                'before_skip', 'after_skip'
            ]
            
            needs_defaults = {
                'title_font_size': r'\large\bfseries',
                'title_color': '#FFFFFF',
                'title_background_color': '#0092FA',
                'title_icon': '',
                'title_icon_size': '',
                'title_icon_color': '#FFFFFF',
                'title_icon_raise': '0pt',
                'title_icon_raise_offset': '0pt',
                'metadata_background_color': '#E9ECEF',
                'metadata_font_size': r'\small',
                'metadata_font_color': '#495057',
                'metadata_key_color': '#212529',
                'metadata_key_font_size': '',
                'content_background_color': '#FFFFFF',
                'content_font_size': r'\normalsize',
                'content_font_color': '#000000',
                'segmentation_style': 'solid',
                'before_skip': '1.5em plus 0.5em minus 0.5em',
                'after_skip': '1.5em plus 0.5em minus 0.5em'
            }

            for p in needs_props:
                val = getattr(config, f'docdash_needs_{p}', None)
                if val is None:
                    if p == 'segmentation_color':
                        # Default segmentation color to title background color
                        val = template_vars.get('docdash_needs_title_background_color', needs_defaults['title_background_color'])
                    else:
                        val = needs_defaults.get(p, '')
                
                # Image Path Icon Detection
                if p == 'title_icon' and val and not val.strip().startswith('\\') and not val.strip().startswith('<'):
                    if val not in config.latex_additional_files:
                        config.latex_additional_files.append(val)
                    base_filename = os.path.basename(val)
                    val = f"\\includegraphics[height=1em, keepaspectratio]{{{base_filename}}}"
                
                # Segmentation Line Handling for manual TikZ \draw injection
                if p == 'segmentation_style':
                    val_str = str(val).lower()
                    if val_str in ['none', 'hidden', 'false', '0', '', 'empty']:
                        val = 'draw=none'
                    else:
                        val = f"{val_str}, draw=ddneed@seglinefg, line width=0.5pt"

                template_vars[f'docdash_needs_{p}'] = val
                
                # Pre-calculate CMYK for colors
                if p.endswith('_color'):
                    template_vars[f'docdash_needs_{p}_cmyk'] = hex_to_cmyk_string(val)

            # Auto-calculate vertical position using robust total bounding box math
            v_pos = getattr(config, 'docdash_needs_title_vertical_position', None)
            manual_raise = getattr(config, 'docdash_needs_title_icon_raise', None)
            offset = getattr(config, 'docdash_needs_title_icon_raise_offset', '0pt')
            
            if not offset:
                offset = '0pt'

            if v_pos == 'middle':
                # Aligns the exact center of the icon with the exact cap-height of the font, plus manual offset
                template_vars['docdash_needs_title_icon_raise'] = rf'\dimexpr 0.5\fontcharht\font`X - 0.5\height + {offset} \relax'
            elif v_pos == 'top':
                template_vars['docdash_needs_title_icon_raise'] = rf'\dimexpr 0.7em - \height + {offset} \relax'
            elif v_pos == 'bottom':
                template_vars['docdash_needs_title_icon_raise'] = offset
            else:
                base_raise = manual_raise if manual_raise is not None else '0pt'
                template_vars['docdash_needs_title_icon_raise'] = rf'\dimexpr {base_raise} + {offset} \relax'

        template_vars['v'] = template_vars
        my_preamble = template.render(**template_vars)
    else:
        logger.warning("[DocDash PDF Theme] Could not find preamble.tex_t template.")
        my_preamble = ""

    # 5. Build the Dynamic Font Package String
    main_font_options = f"[{config.docdash_main_font_options}]" if config.docdash_main_font_options else ""
    
    dynamic_fontpkg = f"""
\\makeatletter
\\AddToHook{{package/capt-of/before}}{{\\let\\captionof\\undefined}}
\\providecommand{{\\py@HeaderFamily}}{{\\sffamily\\bfseries}}
\\makeatother

\\usepackage{{fontspec}}
\\setmainfont{{{config.docdash_main_font}}}{main_font_options}
\\setsansfont{{{config.docdash_sans_font}}}
\\setmonofont{{{config.docdash_mono_font}}}
"""

    # 6. Define Defaults
    default_elements = {
        'fncychap': '',
        'tableofcontents': '\\tableofcontents',
        'papersize': 'a4paper',
        'pointsize': '11pt',
        'extraclassoptions': 'openright,twoside,parskip=half,numbers=noenddot',
        'fontpkg': dynamic_fontpkg
    }

    # Inject defaults without overwriting user configs
    for key, value in default_elements.items():
        if key not in config.latex_elements:
            config.latex_elements[key] = value

    # --- SMART SPHINXSETUP MERGING ---
    user_sphinxsetup = config.latex_elements.get('sphinxsetup', '')
    setup_defaults = [
        ('hmargin', 'hmargin={2cm,3cm}'),
        ('vmargin', 'vmargin={2cm,2.5cm}'),
        ('marginpar', 'marginpar=2cm')
    ]
    
    missing_setups = []
    for key, default_val in setup_defaults:
        if key not in user_sphinxsetup:
            missing_setups.append(default_val)
            
    if missing_setups:
        if user_sphinxsetup:
            config.latex_elements['sphinxsetup'] = user_sphinxsetup.rstrip(', ') + ', ' + ', '.join(missing_setups)
        else:
            config.latex_elements['sphinxsetup'] = ', '.join(missing_setups)
    # ---------------------------------

    # ALWAYS append our preamble so the `normal` pagestyle fix isn't lost
    if 'preamble' in config.latex_elements:
        config.latex_elements['preamble'] += f"\n{my_preamble}"
    else:
        config.latex_elements['preamble'] = my_preamble

    # 7. Logo and Additional Files Handling
    if config.latex_logo and config.latex_logo not in config.latex_additional_files:
        config.latex_additional_files.append(config.latex_logo)

    sty_dir = pkg_dir / "latex_styles"
    config.latex_additional_files.extend([
        str(sty_dir / "sphinxlatexstyleheadings.sty"),
        str(sty_dir / "sphinxlatexstylepage.sty")
    ])

def build_finished(app, exception):
    """Fired when the Sphinx build is complete."""
    if exception is not None or app.builder.name != 'latex':
        return
    
    safe_project = get_safe_filename(app.config.project)
    
    xmp_content = f"""\\Author{{{app.config.author}}}
\\Title{{{app.config.project}}}
\\Subject{{{app.config.project} Documentation}}
\\Copyright{{{(getattr(app.config, 'copyright', ''))}}}
\\Copyrighted{{True}}
\\PublicationType{{Manual}}
"""
    xmp_path = Path(app.builder.outdir) / f"{safe_project}.xmpdata"
    xmp_path.write_text(xmp_content, encoding='utf-8')


def process_needs_ast(app, doctree, docname):
    """Invincible AST Flattener for Sphinx Needs to ensure tcolorbox rendering."""
    if getattr(app.builder, 'format', '') != 'latex':
        return
        
    for node in list(doctree.traverse(nodes.Element)):
        classes = node.get('classes', [])
        if 'need' not in classes and 'need_node' not in classes and node.tagname != 'need':
            continue
            
        if node.get('docdash_processed'):
            continue
        for child in node.traverse(nodes.Element):
            child['docdash_processed'] = True

        # Extract the exact primary Needs ID
        node_ids = node.attributes.get('ids', [])
        nid = node_ids[0] if node_ids else None
        if not nid:
            for child in node.traverse(nodes.target):
                if child.get('ids'):
                    nid = child['ids'][0]
                    break
        if not nid:
            continue

        # CRITICAL FIX: Extract ALL IDs from every single element inside the need node
        # before we destroy it, so no hyperref anchors are lost!
        all_ids = []
        for n in node.traverse(nodes.Element):
            if 'ids' in n.attributes:
                all_ids.extend(n.attributes['ids'])
                
        # Remove duplicates while preserving order
        unique_ids = list(dict.fromkeys(all_ids))
        
        # Sphinx-Needs internally maps cross-references to the "needs:" namespace,
        # so we forcefully ensure it exists as a fallback anchor.
        if nid and f"needs:{nid}" not in unique_ids:
            unique_ids.append(f"needs:{nid}")

        title = ''
        if hasattr(app.env, 'needs_all_needs') and nid in app.env.needs_all_needs:
            title = app.env.needs_all_needs[nid].get('title', '')

        # SANITIZER to absolutely nuke any possibility of a pgfkeys runaway paragraph
        def esc(s):
            if not s: return ''
            return str(s).replace('_', r'\_').replace('%', r'\%').replace('$', r'\$').replace('#', r'\#').replace('&', r'\&').replace('{', r'\{').replace('}', r'\}').replace('\n', ' ').replace('\r', '').strip()

        safe_nid = esc(nid)
        safe_title = esc(title)
        title_str = f"{safe_nid}: {safe_title}" if safe_title else safe_nid
        
        labels_tex = "".join([f"\\phantomsection\\label{{\\detokenize{{{i}}}}}" for i in unique_ids])

        # Construct the new raw LaTeX wrapped tree
        wrapper = nodes.container(classes=['docdash-flat-need'])
        wrapper.append(nodes.raw('', f'\n{labels_tex}\n\\begin{{docdashneedbox}}{{{title_str}}}\n', format='latex'))

        metadata_table = next(iter(node.traverse(nodes.table)), None)
        
        # Flawless Table Demolition and Content Extraction
        if metadata_table:
            rows = list(metadata_table.traverse(nodes.row))
            if len(rows) > 0:
                # In Sphinx-Needs, Row 0 is the Header. Row -1 is ALWAYS the Content.
                # Everything in between is the structural metadata.
                meta_rows = rows[1:-1] if len(rows) > 2 else []
                content_row = rows[-1] if len(rows) > 1 else None

                # 1. Process Metadata
                for row in meta_rows:
                    entries = list(row.traverse(nodes.entry))
                    if len(entries) >= 2:
                        p = nodes.paragraph()
                        p.append(nodes.raw('', r'\needsmetakey{', format='latex'))
                        p.extend(entries[0].children)
                        p.append(nodes.raw('', r'} ', format='latex'))
                        p.extend(entries[1].children)
                        wrapper.append(p)
                    else:
                        for entry in entries:
                            # CRITICAL FIX: Intercept the hidden needs_label tag in single-column layouts
                            for inline_node in list(entry.traverse(nodes.inline)):
                                if 'needs_label' in inline_node.get('classes', []):
                                    wrap = nodes.inline()
                                    wrap.append(nodes.raw('', r'\needsmetakey{', format='latex'))
                                    wrap.extend(inline_node.children)
                                    wrap.append(nodes.raw('', r'}', format='latex'))
                                    inline_node.replace_self(wrap)
                                    
                            p = nodes.paragraph()
                            p.extend(entry.children)
                            wrapper.append(p)

                # 2. Trigger lower box color and process Content!
                if content_row:
                    wrapper.append(nodes.raw('', '\n\\tcblower\n', format='latex'))
                    for entry in content_row.traverse(nodes.entry):
                        wrapper.extend(entry.children)

        wrapper.append(nodes.raw('', '\n\\end{docdashneedbox}\n', format='latex'))
        
        # Demolish the original table and replace it with our flat structure
        node.replace_self(wrapper)


def setup(app):
    # --- SPHINX LATEX WRITER PATCH (ADMONITIONS) ---
    _orig_visit_admonition = LaTeXTranslator.visit_admonition
    def _custom_visit_admonition(self, node):
        _orig_visit_admonition(self, node)
        if self.body and '{note}' in self.body[-1]:
            self.body[-1] = self.body[-1].replace('{note}', '{admonition}')
    LaTeXTranslator.visit_admonition = _custom_visit_admonition
    # ---------------------------------

    app.add_directive('stylebox', StyleBoxDirective)

    # General Theme Settings
    app.add_config_value('docdash_title_page_top_line', False, 'env')
    app.add_config_value('docdash_title_page_background_image', None, 'env')
    app.add_config_value('docdash_title_page_color_opacity', None, 'env')
    app.add_config_value('docdash_footer_logo', None, 'env')
    app.add_config_value('docdash_footer_logo_height', '1.5em', 'env')
    app.add_config_value('docdash_headsep', '8mm', 'env')
    app.add_config_value('docdash_footskip', '10mm', 'env')
    app.add_config_value('docdash_headheight', '18pt', 'env')
    app.add_config_value('docdash_footheight', '25pt', 'env')

    # Toggles & Text
    app.add_config_value('docdash_subtitle', None, 'env')
    app.add_config_value('docdash_show_release', True, 'env')
    app.add_config_value('docdash_numbers_in_margin', True, 'env')
    
    app.add_config_value('docdash_containers', {}, 'env')
    app.add_config_value('docdash_part_backgrounds', {}, 'env')
    app.add_config_value('docdash_draft_text', None, 'env')
    app.add_config_value('docdash_draft_color', '#00000044', 'env')
    app.add_config_value('docdash_draft_date_format', '%Y-%m-%d %H:%M:%S', 'env')
    app.add_config_value('docdash_draft_font', None, 'env')
    app.add_config_value('docdash_draft_font_size', r'\Huge\bfseries\sffamily', 'env')
    
    # Alignment Toggles
    app.add_config_value('docdash_heading_align', 'alternate', 'env')
    app.add_config_value('docdash_heading_margin_space', '1.5em', 'env')
    for el in ['chapter', 'section', 'subsection', 'subsubsection']:
        app.add_config_value(f'docdash_{el}_align', None, 'env')
        app.add_config_value(f'docdash_{el}_number_margin', None, 'env')
        app.add_config_value(f'docdash_{el}_number_line', None, 'env')
        app.add_config_value(f'docdash_{el}_line_height', None, 'env')
        app.add_config_value(f'docdash_{el}_margin_space', None, 'env')

    # Inheritance Toggles
    app.add_config_value('docdash_inherit_all', True, 'env')
    app.add_config_value('docdash_inherit_font', True, 'env')
    app.add_config_value('docdash_inherit_color', True, 'env')
    app.add_config_value('docdash_inherit_size', False, 'env')

    # Core Base Fonts
    app.add_config_value('docdash_main_font', 'Lato Light', 'env')
    app.add_config_value('docdash_main_font_options', 'BoldFont={Lato Regular}, ItalicFont={Lato Light Italic}, BoldItalicFont={Lato Italic}', 'env')
    app.add_config_value('docdash_sans_font', 'Exo 2', 'env')
    app.add_config_value('docdash_mono_font', 'IosevkaTerm NF', 'env')

    # Register Universal Element Customization Namespace
    elements = [
        'title_page', 'title', 'subtitle', 'author', 'date', 'release_version', 
        'part', 'chapter', 'section', 'subsection', 'subsubsection', 'rubric',
        'part_number', 'part_number_part', 'part_number_number', 
        'chapter_number', 'section_number', 'subsection_number', 'subsubsection_number',
        'chapter_line', 'section_line', 'subsection_line', 'subsubsection_line'
    ]

    for el in elements:
        for attr in ['font', 'color', 'size']:
            key = f'{el}_{attr}'
            app.add_config_value(f'docdash_{key}', None, 'env')

    # Admonition Customization Namespace
    admon_types = ['generic', 'admonition', 'note', 'warning', 'hint', 'danger', 'error', 'caution', 'tip', 'important', 'attention']
    admon_props = [
        'title_icon', 'title_icon_color', 'title_icon_size', 'title_icon_padding', 'title_decoration_spacing', 
        'title_font', 'title_font_color', 'title_font_size', 
        'title_background_color', 'title_icon_box_background_color', 
        'content_background_color', 'content_background_color_nested', 
        'content_font', 'content_font_color', 'content_font_size',
        'before_skip', 'after_skip'
    ]

    for t in admon_types:
        for p in admon_props:
            app.add_config_value(f'docdash_admonition_{t}_{p}', None, 'env')

    # Sphinx Needs Customization Namespace
    needs_props = [
        'title_font', 'title_font_size', 'title_color', 'title_background_color',
        'title_icon', 'title_icon_size', 'title_icon_color', 'title_icon_raise', 'title_icon_raise_offset', 'title_vertical_position',
        'metadata_background_color', 'metadata_font', 'metadata_font_size', 'metadata_font_color',
        'metadata_key_font', 'metadata_key_color', 'metadata_key_font_size',
        'content_background_color', 'content_font', 'content_font_size', 'content_font_color',
        'segmentation_style', 'segmentation_color',
        'before_skip', 'after_skip'
    ]
    for p in needs_props:
        app.add_config_value(f'docdash_needs_{p}', None, 'env')

    app.connect('config-inited', config_inited, priority=900)
    app.connect('build-finished', build_finished)
    
    # Run the AST Flattener securely at the very end of AST resolution
    app.connect('doctree-resolved', process_containers_ast, priority=998)
    app.connect('doctree-resolved', process_needs_ast, priority=999)
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }