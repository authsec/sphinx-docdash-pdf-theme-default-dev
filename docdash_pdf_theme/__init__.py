import os
import re
from pathlib import Path
from sphinx.util import logging
from jinja2 import Environment
from sphinx.writers.latex import LaTeXTranslator

logger = logging.getLogger(__name__)

__version__ = "0.1.45"

def get_safe_filename(name: str) -> str:
    """Creates a filesystem-safe string from a project name."""
    safe = re.sub(r'[^A-Za-z0-9\s]+', '', name).strip().replace(' ', '_')
    return safe.lower() or "document"

def hex_to_cmyk_string(hex_color: str) -> str:
    """Converts a hex color string (e.g., '#FF0000') to a LaTeX CMYK string."""
    if not hex_color:
        return None
        
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        logger.warning(f"[DocDash] Invalid hex color '{hex_color}'. Falling back to black.")
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
            'docdash_headsep': getattr(config, 'docdash_headsep', None),
            'docdash_footskip': getattr(config, 'docdash_footskip', None),
            'docdash_headheight': getattr(config, 'docdash_headheight', None),
            'docdash_footheight': getattr(config, 'docdash_footheight', None),
        }

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
            'content_font_size': r'\normalsize'
        }

        admon_types = ['generic', 'admonition', 'note', 'warning', 'hint', 'danger', 'error', 'caution', 'tip', 'important', 'attention']
        admon_props = [
            'title_icon', 'title_icon_color', 'title_icon_size', 'title_icon_padding', 'title_decoration_spacing', 
            'title_font', 'title_font_color', 'title_font_size', 
            'title_background_color', 'title_icon_box_background_color', 
            'content_background_color', 'content_background_color_nested', 
            'content_font', 'content_font_color', 'content_font_size'
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
        ('hmargin', 'hmargin={1.5cm,2.5cm}'),
        ('vmargin', 'vmargin={2cm,2cm}'),
        ('marginpar', 'marginpar=2.5cm')
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

def setup(app):
    # --- SPHINX LATEX WRITER PATCH ---
    # By default, Sphinx's LaTeX writer forcefully converts generic `.. admonition::` directives 
    # to use the "note" environment. We intercept this so our theme can style it independently!
    _orig_visit_admonition = LaTeXTranslator.visit_admonition
    def _custom_visit_admonition(self, node):
        _orig_visit_admonition(self, node)
        # Safely replace the hardcoded {note} with {admonition} right after Sphinx appends it
        if self.body and '{note}' in self.body[-1]:
            self.body[-1] = self.body[-1].replace('{note}', '{admonition}')
    LaTeXTranslator.visit_admonition = _custom_visit_admonition
    # ---------------------------------

    # General Theme Settings
    app.add_config_value('docdash_footer_logo', None, 'env')
    app.add_config_value('docdash_footer_logo_height', '1.5em', 'env')
    app.add_config_value('docdash_headsep', None, 'env')
    app.add_config_value('docdash_footskip', None, 'env')
    app.add_config_value('docdash_headheight', None, 'env')
    app.add_config_value('docdash_footheight', None, 'env')

    # Toggles & Text
    app.add_config_value('docdash_subtitle', None, 'env')
    app.add_config_value('docdash_show_release', True, 'env')
    app.add_config_value('docdash_numbers_in_margin', True, 'env')
    
    # Alignment Toggles
    app.add_config_value('docdash_heading_align', 'alternate', 'env') # 'alternate', 'left', 'right'
    app.add_config_value('docdash_heading_margin_space', '1.5em', 'env') # Global default space
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

    # Register Universal Element Customization Namespace with NO defaults
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
        'content_font', 'content_font_color', 'content_font_size'
    ]

    for t in admon_types:
        for p in admon_props:
            app.add_config_value(f'docdash_admonition_{t}_{p}', None, 'env')

    app.connect('config-inited', config_inited, priority=900)
    app.connect('build-finished', build_finished)
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }