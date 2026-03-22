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

__version__ = "0.1.137"

# --- DEFAULT CONTAINER TITLE STYLES ---
# These are used if the user does not provide a custom {style_name}.tex file in their confdir.
DEFAULT_TITLE_STYLES = {
    'classic': r"attach boxed title to top left={xshift=0pt, yshift=0pt}, boxed title style={empty, left=1ex, right=0pt}",
    'floating': r"""attach boxed title to top left={xshift=-4mm,yshift=-0.5mm},
varwidth boxed title=0.7\linewidth,
boxed title style={empty,arc=0pt,outer arc=0pt,boxrule=0pt},
underlay boxed title={
  \fill[#1] (title.north west) -- (title.north east) -- +(\tcboxedtitleheight-1mm,-\tcboxedtitleheight+1mm) -- ([xshift=4mm,yshift=0.5mm]frame.north east) -- +(0mm,-1mm) -- (title.south west) -- cycle;
  \fill[#1!50!black] ([yshift=-0.5mm]frame.north west) -- +(-0.4,0) -- +(0,-0.3) -- cycle;
  \fill[#1!50!black] ([yshift=-0.5mm]frame.north east) -- +(0,-0.3) -- +(0.4,0) -- cycle;
}""",
    'ribbon': r"""attach boxed title to top left={xshift=1cm,yshift*=1mm-\tcboxedtitleheight},
varwidth boxed title*=-3cm,
boxed title style={
  frame code={
    \path[fill=tcbcolback!30!black] ([yshift=-1mm,xshift=-1mm]frame.north west) arc[start angle=0,end angle=180,radius=1mm] ([yshift=-1mm,xshift=1mm]frame.north east) arc[start angle=180,end angle=0,radius=1mm];
    \path[left color=tcbcolback!60!black,right color=tcbcolback!60!black, middle color=tcbcolback!80!black] ([xshift=-2mm]frame.north west) -- ([xshift=2mm]frame.north east) [rounded corners=1mm]-- ([xshift=1mm,yshift=-1mm]frame.north east) -- (frame.south east) -- (frame.south west) -- ([xshift=-1mm,yshift=-1mm]frame.north west) [sharp corners]-- cycle;
  },
  interior engine=empty
}"""
}

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

def process_epigraph_ast(app, doctree, docname):
    """Replaces Sphinx epigraph nodes with KOMA-Script dictum macros, handling part/chapter preambles."""
    if getattr(app.builder, 'format', '') != 'latex':
        return
        
    toplevel = getattr(app.config, 'latex_toplevel_sectioning', None)
    if not toplevel:
        docclass = app.config.latex_docclass.get('manual', 'scrbook')
        toplevel = 'chapter' if docclass in ('scrbook', 'book', 'report') else 'section'
        
    for node in list(doctree.traverse(nodes.block_quote)):
        if 'epigraph' not in node.get('classes', []):
            continue
        if node.get('docdash_processed'):
            continue
        node['docdash_processed'] = True
        
        # Calculate section depth and determine sec_type
        p = node.parent
        depth = 0
        while p:
            if isinstance(p, nodes.section):
                depth += 1
            p = p.parent
            
        sec_type = 'generic'
        if toplevel == 'part':
            type_map = {1: 'part', 2: 'chapter', 3: 'section', 4: 'subsection', 5: 'subsubsection'}
        else:
            type_map = {1: 'chapter', 2: 'section', 3: 'subsection', 4: 'subsubsection'}
        
        if depth in type_map:
            sec_type = type_map[depth]
            
        # Determine if this is a true KOMA preamble (first element under a heading)
        is_preamble = False
        idx = -1
        parent = node.parent
        if isinstance(parent, nodes.section):
            idx = parent.children.index(node)
            if idx > 0 and isinstance(parent.children[idx-1], nodes.title):
                is_preamble = True
                
        attr = None
        for child in node:
            if isinstance(child, nodes.attribution):
                attr = child
                break
        
        wrapper = nodes.container(classes=['docdash-dictum'])
        
        # If it is a structural preamble, inject the KOMA preamble macro and setup the styling
        if is_preamble and sec_type in ('part', 'chapter'):
            wrapper.append(nodes.raw('', f'\\set{sec_type}preamble[u]{{\n\\begingroup\n\\setupddepigraph{{{sec_type}}}\n', format='latex'))
        else:
            wrapper.append(nodes.raw('', f'\\begingroup\n\\setupddepigraph{{{sec_type}}}\n', format='latex'))
        
        # Construct the standard KOMA dictum
        if attr:
            node.remove(attr)
            wrapper.append(nodes.raw('', '\\dictum[{', format='latex'))
            
            # Unwrap paragraph nodes in attribution so KOMA doesn't crash on \par
            for child in attr.children:
                if isinstance(child, nodes.paragraph):
                    for gc in child.children:
                        wrapper.append(gc)
                else:
                    wrapper.append(child)
                    
            wrapper.append(nodes.raw('', '}]{', format='latex'))
        else:
            wrapper.append(nodes.raw('', '\\dictum{', format='latex'))
        
        # Add the remaining quote text
        for child in node.children:
            wrapper.append(child)
            
        wrapper.append(nodes.raw('', '}\n\\endgroup\n', format='latex'))
        
        # Close the structural preamble if active, and perform AST Surgery to move it before the title
        if is_preamble and sec_type in ('part', 'chapter'):
            wrapper.append(nodes.raw('', '}\n', format='latex'))
            parent.remove(node)
            parent.insert(idx - 1, wrapper)
        else:
            node.replace_self(wrapper)

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

def config_inited(app, config):
    """Fired when Sphinx finishes reading conf.py. Translates dict configs to flat Jinja variables."""
    
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
        
        template_vars = {}
        
        # Pull dictionaries from Sphinx config
        tp = getattr(config, 'docdash_title_page', {})
        headings = getattr(config, 'docdash_headings', {})
        parts = getattr(config, 'docdash_parts', {})
        draft = getattr(config, 'docdash_draft', {})
        epigraphs = getattr(config, 'docdash_epigraphs', {})
        admonitions = getattr(config, 'docdash_admonitions', {})
        needs = getattr(config, 'docdash_needs', {})
        containers = getattr(config, 'docdash_containers', {})

        # --- CONTAINERS ---
        safe_containers = {}
        loaded_title_styles = {}
        
        for c_name, c_conf in containers.items():
            # Sanitize the class name for LaTeX variables
            safe_name = re.sub(r'[^a-zA-Z]', '', c_name)
            
            title_color = c_conf.get('title_color', '#000000')
            c_conf['title_color_cmyk'] = hex_to_cmyk_string(title_color)
            
            title_text_color = c_conf.get('title_font_color', get_highest_contrast_color(title_color, title_color, target='foreground'))
            c_conf['title_font_color_cmyk'] = hex_to_cmyk_string(title_text_color)
            
            # Default icon color to the title text color if missing
            icon_color = c_conf.get('title_icon_color', title_text_color)
            c_conf['title_icon_color_cmyk'] = hex_to_cmyk_string(icon_color)
            
            c_conf['content_font_color_cmyk'] = hex_to_cmyk_string(c_conf.get('content_font_color', '#000000'))
            c_conf['content_background_color_cmyk'] = hex_to_cmyk_string(c_conf.get('content_background_color', '#FFFFFF'))
            c_conf.setdefault('title_font_size', r'\large\bfseries')
            c_conf.setdefault('title_icon_font_size', '')
            c_conf.setdefault('content_font_size', r'\normalsize')
            
            # TITLE STYLE RESOLUTION ENGINE
            style_name = c_conf.get('title_style', 'classic')
            if style_name not in loaded_title_styles:
                # 1. Try to load from user's confdir
                custom_style_path = Path(app.confdir) / f"{style_name}.tex"
                if custom_style_path.exists():
                    raw_content = custom_style_path.read_text(encoding='utf-8')
                # 2. Try to load from internal default dict
                elif style_name in DEFAULT_TITLE_STYLES:
                    raw_content = DEFAULT_TITLE_STYLES[style_name]
                else:
                    logger.warning(f"[DocDash] Container title style '{style_name}' not found as '{style_name}.tex'. Falling back to 'classic'.")
                    style_name = 'classic'
                    if 'classic' not in loaded_title_styles:
                        raw_content = DEFAULT_TITLE_STYLES['classic']
                        
                # Compress the raw content into a single line to prevent pgfkeys runaway argument errors
                if style_name not in loaded_title_styles:
                    flattened = " ".join(line.strip() for line in raw_content.splitlines() if line.strip())
                    loaded_title_styles[style_name] = flattened
                        
            c_conf['title_style'] = style_name
            
            # Prevent string conversion bugs (e.g. "False" instead of False)
            frame_val = c_conf.get('container_frame', True)
            if isinstance(frame_val, str):
                frame_val = frame_val.lower() not in ['false', '0', 'none', 'no']
            c_conf['container_frame'] = frame_val
            
            # Extract boolean for text width alignment
            match_val = c_conf.get('match_text_width', False)
            if isinstance(match_val, str):
                match_val = match_val.lower() not in ['false', '0', 'none', 'no']
            c_conf['match_text_width'] = match_val
            
            c_conf.setdefault('title_icon', '')
            c_conf.setdefault('title_font', '')
            c_conf.setdefault('content_font', '')
            
            safe_containers[safe_name] = c_conf
            
        template_vars['docdash_containers'] = safe_containers
        template_vars['docdash_loaded_title_styles'] = loaded_title_styles

        # --- GLOBALS ---
        template_vars['docdash_show_release'] = getattr(config, 'docdash_show_release', True)
        template_vars['docdash_headsep'] = getattr(config, 'docdash_headsep', '8mm')
        template_vars['docdash_footskip'] = getattr(config, 'docdash_footskip', '10mm')
        template_vars['docdash_headheight'] = getattr(config, 'docdash_headheight', '18pt')
        template_vars['docdash_footheight'] = getattr(config, 'docdash_footheight', '25pt')
        template_vars['extensions'] = getattr(config, 'extensions', [])

        # Footer Logo
        footer_logo = getattr(config, 'docdash_footer_logo', None)
        if footer_logo and isinstance(footer_logo, str):
            if footer_logo not in config.latex_additional_files:
                config.latex_additional_files.append(footer_logo)
            template_vars['docdash_footer_logo'] = os.path.basename(footer_logo)
        else:
            template_vars['docdash_footer_logo'] = None
        template_vars['docdash_footer_logo_height'] = getattr(config, 'docdash_footer_logo_height', '1.5em')

        # --- TITLE PAGE ---
        template_vars['docdash_subtitle'] = tp.get('subtitle', None)
        template_vars['docdash_title_page_color'] = hex_to_cmyk_string(tp.get('page_color', None))
        template_vars['docdash_title_page_top_line'] = tp.get('top_line', False)
        
        title_bg = tp.get('background_image', None)
        if title_bg and isinstance(title_bg, str):
            if title_bg not in config.latex_additional_files:
                config.latex_additional_files.append(title_bg)
            template_vars['docdash_title_page_background_image'] = os.path.basename(title_bg)
        else:
            template_vars['docdash_title_page_background_image'] = None

        opacity = tp.get('color_opacity', None)
        if opacity is None:
            opacity = '0.5' if template_vars['docdash_title_page_background_image'] else '1.0'
        template_vars['docdash_title_page_color_opacity'] = opacity
        
        for el in ['title', 'subtitle', 'author', 'date', 'release_version']:
            prefix = f'{el}_' if el != 'title' else ''
            template_vars[f'docdash_{el}_font'] = tp.get(f'{prefix}font', None)
            template_vars[f'docdash_{el}_size'] = tp.get(f'{prefix}size', None)
            template_vars[f'docdash_{el}_color'] = hex_to_cmyk_string(tp.get(f'{prefix}color', None))

        # --- DRAFT ---
        draft_text = draft.get('text', None)
        if draft_text:
            date_fmt = draft.get('date_format', '%Y-%m-%d %H:%M:%S')
            formatted_date = datetime.now().strftime(date_fmt)
            ext_version = __version__
            proj_version = getattr(config, 'version', getattr(config, 'release', ''))
            
            draft_text = draft_text.replace('{date}', formatted_date)
            draft_text = draft_text.replace('{ext_version}', ext_version)
            draft_text = draft_text.replace('{project_version}', proj_version)
            template_vars['docdash_draft_text'] = draft_text
            
            draft_color_str = draft.get('color', '#00000044')
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

            template_vars['docdash_draft_font'] = draft.get('font', None)
            template_vars['docdash_draft_font_size'] = draft.get('font_size', r'\Huge\bfseries\sffamily')
        else:
            template_vars['docdash_draft_text'] = None

        # --- PARTS ---
        processed_part_bgs = {}
        if getattr(config, 'latex_toplevel_sectioning', '') == 'part':
            for p_num, p_conf in parts.items():
                if not isinstance(p_num, int):
                    continue
                
                img = p_conf.get('image', None)
                if img:
                    if img not in config.latex_additional_files:
                        config.latex_additional_files.append(img)
                    img = os.path.basename(img)
                
                color_str = p_conf.get('background_color', p_conf.get('color', None))
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
                    
                processed_part_bgs[p_num] = {
                    'image': img,
                    'background_color_cmyk': cmyk,
                    'opacity': opacity,
                    'epigraph_color_cmyk': hex_to_cmyk_string(p_conf.get('epigraph_color', None)),
                    'epigraph_author_color_cmyk': hex_to_cmyk_string(p_conf.get('epigraph_author_color', None)),
                    'font_color_cmyk': hex_to_cmyk_string(p_conf.get('font_color', None)),
                    'font': p_conf.get('font', None),
                    'size': p_conf.get('size', None),
                    'number_color_cmyk': hex_to_cmyk_string(p_conf.get('number_color', None)),
                    'number_font': p_conf.get('number_font', None),
                    'number_size': p_conf.get('number_size', None),
                    'number_part_color_cmyk': hex_to_cmyk_string(p_conf.get('number_part_color', None)),
                    'number_part_font': p_conf.get('number_part_font', None),
                    'number_part_size': p_conf.get('number_part_size', None),
                    'number_number_color_cmyk': hex_to_cmyk_string(p_conf.get('number_number_color', None)),
                    'number_number_font': p_conf.get('number_number_font', None),
                    'number_number_size': p_conf.get('number_number_size', None),
                }
        template_vars['docdash_part_backgrounds'] = processed_part_bgs

        # Global Part Fonts/Colors
        for el in ['part', 'part_number', 'part_number_part', 'part_number_number']:
            prefix = el.replace('part_', '') + '_' if el != 'part' else ''
            template_vars[f'docdash_{el}_font'] = parts.get(f'{prefix}font', None)
            template_vars[f'docdash_{el}_size'] = parts.get(f'{prefix}size', None)
            template_vars[f'docdash_{el}_color'] = hex_to_cmyk_string(parts.get(f'{prefix}color', None))

        # --- HEADINGS ---
        global_align = headings.get('align', 'alternate')
        global_margin = headings.get('numbers_in_margin', True)
        global_margin_space = headings.get('margin_space', '1.5em')
        
        for el in ['chapter', 'section', 'subsection', 'subsubsection']:
            el_dict = headings.get(el, {})
            
            template_vars[f'docdash_{el}_align'] = el_dict.get('align', global_align)
            template_vars[f'docdash_{el}_number_margin'] = el_dict.get('number_margin', global_margin)
            template_vars[f'docdash_{el}_number_line'] = el_dict.get('number_line', True if el == 'chapter' else False)
            template_vars[f'docdash_{el}_line_height'] = el_dict.get('line_height', '10cm')
            template_vars[f'docdash_{el}_margin_space'] = el_dict.get('margin_space', global_margin_space)
            
            template_vars[f'docdash_{el}_font'] = el_dict.get('font', None)
            template_vars[f'docdash_{el}_size'] = el_dict.get('size', None)
            template_vars[f'docdash_{el}_color'] = hex_to_cmyk_string(el_dict.get('color', None))
            
            template_vars[f'docdash_{el}_number_font'] = el_dict.get('number_font', None)
            template_vars[f'docdash_{el}_number_size'] = el_dict.get('number_size', None)
            template_vars[f'docdash_{el}_number_color'] = hex_to_cmyk_string(el_dict.get('number_color', None))
            
            template_vars[f'docdash_{el}_line_color'] = hex_to_cmyk_string(el_dict.get('line_color', None))

        # --- EPIGRAPHS ---
        align_map = {'left': r'\raggedright', 'right': r'\raggedleft', 'center': r'\centering'}
        
        template_vars['docdash_epigraph_width'] = epigraphs.get('width', '0.5\\textwidth')
        base_format = epigraphs.get('format', '--- #1')
        template_vars['docdash_epigraph_format'] = base_format.replace('#1', '##1')
        
        template_vars['docdash_epigraph_align_box'] = align_map.get(epigraphs.get('align_box', 'right'), r'\raggedleft')
        template_vars['docdash_epigraph_align_text'] = align_map.get(epigraphs.get('align_text', 'left'), r'\raggedright')
        template_vars['docdash_epigraph_align_author'] = align_map.get(epigraphs.get('align_author', 'right'), r'\raggedleft')

        template_vars['docdash_epigraph_font'] = epigraphs.get('font', None)
        template_vars['docdash_epigraph_size'] = epigraphs.get('size', None)
        template_vars['docdash_epigraph_color'] = hex_to_cmyk_string(epigraphs.get('color', None))
        
        template_vars['docdash_epigraph_author_font'] = epigraphs.get('author_font', None)
        template_vars['docdash_epigraph_author_size'] = epigraphs.get('author_size', None)
        template_vars['docdash_epigraph_author_color'] = hex_to_cmyk_string(epigraphs.get('author_color', None))

        levels = ['part', 'chapter', 'section', 'subsection', 'subsubsection']
        for idx, level in enumerate(levels):
            el_dict = epigraphs.get(level, {})
            
            for prop in ['width', 'format']:
                val = el_dict.get(prop, None)
                if val is None:
                    val = template_vars.get(f'docdash_{levels[idx-1]}_epigraph_{prop}' if idx > 0 else f'docdash_epigraph_{prop}')
                elif prop == 'format':
                    val = val.replace('#1', '##1')
                template_vars[f'docdash_{level}_epigraph_{prop}'] = val
                
            for prop in ['align_box', 'align_text', 'align_author']:
                val = el_dict.get(prop, None)
                if val is None:
                    val_mapped = template_vars.get(f'docdash_{levels[idx-1]}_epigraph_{prop}' if idx > 0 else f'docdash_epigraph_{prop}')
                else:
                    val_mapped = align_map.get(val, r'\raggedleft' if prop != 'align_text' else r'\raggedright')
                template_vars[f'docdash_{level}_epigraph_{prop}'] = val_mapped
                
            for prop in ['font', 'size', 'color', 'author_font', 'author_size', 'author_color']:
                val = el_dict.get(prop, None)
                if val is None:
                    val = template_vars.get(f'docdash_{levels[idx-1]}_epigraph_{prop}' if idx > 0 else f'docdash_epigraph_{prop}')
                elif 'color' in prop and val:
                    val = hex_to_cmyk_string(val)
                template_vars[f'docdash_{level}_epigraph_{prop}'] = val

        # --- TEXT INHERITANCE LOGIC ---
        if getattr(config, 'docdash_inherit_all', True):
            hierarchies = [
                ['part', 'chapter', 'section', 'subsection', 'subsubsection'],
                ['part_number', 'chapter_number', 'section_number', 'subsection_number', 'subsubsection_number'],
                ['chapter_line', 'section_line', 'subsection_line', 'subsubsection_line'],
                ['epigraph', 'part_epigraph', 'chapter_epigraph', 'section_epigraph', 'subsection_epigraph', 'subsubsection_epigraph'],
                ['epigraph_author', 'part_epigraph_author', 'chapter_epigraph_author', 'section_epigraph_author', 'subsection_epigraph_author', 'subsubsection_epigraph_author']
            ]
            properties = [
                ('font', getattr(config, 'docdash_inherit_font', True)),
                ('color', getattr(config, 'docdash_inherit_color', True)),
                ('size', getattr(config, 'docdash_inherit_size', False))
            ]
            for hierarchy in hierarchies:
                for prop, is_enabled in properties:
                    if is_enabled:
                        current_val = template_vars.get(f'docdash_{hierarchy[0]}_{prop}', None)
                        for i in range(1, len(hierarchy)):
                            level = hierarchy[i]
                            key = f'docdash_{level}_{prop}'
                            if not template_vars.get(key):
                                template_vars[key] = current_val
                            else:
                                current_val = template_vars[key]

        for prop in ['font', 'color', 'size']:
            if not template_vars.get(f'docdash_part_number_part_{prop}'):
                template_vars[f'docdash_part_number_part_{prop}'] = template_vars.get(f'docdash_part_number_{prop}')
            if not template_vars.get(f'docdash_part_number_number_{prop}'):
                template_vars[f'docdash_part_number_number_{prop}'] = template_vars.get(f'docdash_part_number_{prop}')

        # --- ADMONITIONS ---
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
            t_dict = admonitions.get(t, {})
            for p in admon_props:
                val = t_dict.get(p, None)
                
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

        # Dynamic caution contrast fallback if missing
        caution_bg = template_vars.get('docdash_admonition_caution_title_background_color')
        caution_box_bg = template_vars.get('docdash_admonition_caution_title_icon_box_background_color')
        if admonitions.get('caution', {}).get('title_icon_color') is None:
            safe_icon_color = get_highest_contrast_color(caution_bg, caution_box_bg)
            template_vars['docdash_admonition_caution_title_icon_color'] = safe_icon_color
            template_vars['docdash_admonition_caution_title_icon_color_cmyk'] = hex_to_cmyk_string(safe_icon_color)

        # --- SPHINX NEEDS ---
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
            val = needs.get(p, None)
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
        v_pos = needs.get('title_vertical_position', None)
        manual_raise = needs.get('title_icon_raise', None)
        offset = needs.get('title_icon_raise_offset', '0pt')
        if not offset: offset = '0pt'

        if v_pos == 'middle':
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

    # ALWAYS append our preamble so the `normal` pagestyle fix isnt lost
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
    app.add_config_value('docdash_footer_logo', None, 'env')
    app.add_config_value('docdash_footer_logo_height', '1.5em', 'env')
    app.add_config_value('docdash_headsep', '8mm', 'env')
    app.add_config_value('docdash_footskip', '10mm', 'env')
    app.add_config_value('docdash_headheight', '18pt', 'env')
    app.add_config_value('docdash_footheight', '25pt', 'env')
    app.add_config_value('docdash_show_release', True, 'env')
    
    # Core Base Fonts
    app.add_config_value('docdash_main_font', 'Lato Light', 'env')
    app.add_config_value('docdash_main_font_options', 'BoldFont={Lato Regular}, ItalicFont={Lato Light Italic}, BoldItalicFont={Lato Italic}', 'env')
    app.add_config_value('docdash_sans_font', 'Exo 2', 'env')
    app.add_config_value('docdash_mono_font', 'IosevkaTerm NF', 'env')
    
    # Inheritance Toggles
    app.add_config_value('docdash_inherit_all', True, 'env')
    app.add_config_value('docdash_inherit_font', True, 'env')
    app.add_config_value('docdash_inherit_color', True, 'env')
    app.add_config_value('docdash_inherit_size', False, 'env')

    # Root Configuration Dictionaries
    app.add_config_value('docdash_title_page', {}, 'env')
    app.add_config_value('docdash_headings', {}, 'env')
    app.add_config_value('docdash_parts', {}, 'env')
    app.add_config_value('docdash_epigraphs', {}, 'env')
    app.add_config_value('docdash_admonitions', {}, 'env')
    app.add_config_value('docdash_needs', {}, 'env')
    app.add_config_value('docdash_draft', {}, 'env')
    app.add_config_value('docdash_containers', {}, 'env')

    app.connect('config-inited', config_inited, priority=900)
    app.connect('build-finished', build_finished)
    
    # Run the AST Flattener securely at the very end of AST resolution
    app.connect('doctree-resolved', process_containers_ast, priority=998)
    app.connect('doctree-resolved', process_epigraph_ast, priority=997)
    app.connect('doctree-resolved', process_needs_ast, priority=999)
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }