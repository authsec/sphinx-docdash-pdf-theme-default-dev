import os
import re
from pathlib import Path
from sphinx.util import logging
from jinja2 import Environment

logger = logging.getLogger(__name__)

__version__ = "0.1.20"

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
            'docdash_numbers_in_margin': getattr(config, 'docdash_numbers_in_margin', True),
            'docdash_title_page_color': hex_to_cmyk_string(getattr(config, 'docdash_title_page_color', None)),
        }
        
        # Dynamically load Universal DocDash Namespace Elements
        elements = [
            'title', 'subtitle', 'author', 'date', 'release_version', 
            'part', 'chapter', 'section', 'subsection', 'subsubsection', 'rubric',
            'part_number', 'part_number_part', 'part_number_number', 
            'chapter_number', 'chapter_line', 'section_number', 'subsection_number', 'subsubsection_number'
        ]
        
        for el in elements:
            template_vars[f'docdash_{el}_font'] = getattr(config, f'docdash_{el}_font', None)
            template_vars[f'docdash_{el}_size'] = getattr(config, f'docdash_{el}_size', None)
            template_vars[f'docdash_{el}_color'] = hex_to_cmyk_string(getattr(config, f'docdash_{el}_color', None))

        # --- INHERITANCE LOGIC ---
        # Resolve inheritance cascading top-down before passing to Jinja template
        if getattr(config, 'docdash_inherit_all', True):
            hierarchies = [
                ['part', 'chapter', 'section', 'subsection', 'subsubsection'],
                ['part_number', 'chapter_number', 'section_number', 'subsection_number', 'subsubsection_number']
            ]
            properties = [
                ('font', getattr(config, 'docdash_inherit_font', True)),
                ('color', getattr(config, 'docdash_inherit_color', True)),
                ('size', getattr(config, 'docdash_inherit_size', False))
            ]
            
            for hierarchy in hierarchies:
                for prop, is_enabled in properties:
                    if is_enabled:
                        # Grab the highest level value (e.g., part_font)
                        current_val = template_vars[f'docdash_{hierarchy[0]}_{prop}']
                        
                        # Loop down the hierarchy
                        for i in range(1, len(hierarchy)):
                            level = hierarchy[i]
                            key = f'docdash_{level}_{prop}'
                            
                            # If the current level isn't explicitly defined (None or empty string), inherit from above
                            if not template_vars[key]:
                                template_vars[key] = current_val
                            # If it IS defined, it becomes the new value to cascade downward
                            else:
                                current_val = template_vars[key]
        # --- END INHERITANCE LOGIC ---

        # Apply specific fallback logic for part_number split components
        for prop in ['font', 'color', 'size']:
            if not template_vars[f'docdash_part_number_part_{prop}']:
                template_vars[f'docdash_part_number_part_{prop}'] = template_vars[f'docdash_part_number_{prop}']
            if not template_vars[f'docdash_part_number_number_{prop}']:
                template_vars[f'docdash_part_number_number_{prop}'] = template_vars[f'docdash_part_number_{prop}']

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
        'sphinxsetup': 'hmargin={1.5cm,2.5cm}, vmargin={2cm,2cm}, marginpar=2.5cm',
        'papersize': 'a4paper',
        'pointsize': '11pt',
        'extraclassoptions': 'openright,twoside,parskip=half,numbers=noenddot',
        'fontpkg': dynamic_fontpkg
    }

    # Inject defaults without overwriting user configs
    for key, value in default_elements.items():
        if key not in config.latex_elements:
            config.latex_elements[key] = value

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
    # Toggles & Text
    app.add_config_value('docdash_subtitle', None, 'env')
    app.add_config_value('docdash_show_release', True, 'env')
    app.add_config_value('docdash_numbers_in_margin', True, 'env')
    
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
        'chapter_number', 'chapter_line', 'section_number', 'subsection_number', 'subsubsection_number'
    ]

    for el in elements:
        for attr in ['font', 'color', 'size']:
            key = f'{el}_{attr}'
            # If not configured by the user, this resolves to None, disabling the logic perfectly
            app.add_config_value(f'docdash_{key}', None, 'env')

    app.connect('config-inited', config_inited, priority=900)
    app.connect('build-finished', build_finished)
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }