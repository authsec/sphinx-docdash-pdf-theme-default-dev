import os
import re
from pathlib import Path
from sphinx.util import logging
from jinja2 import Environment
from sphinx.writers.latex import LaTeXTranslator

logger = logging.getLogger(__name__)

__version__ = "0.1.74"

def get_safe_filename(name: str) -> str:
    """Creates a filesystem-safe string from a project name."""
    safe = re.sub(r'[^A-Za-z0-9\s]+', '', name).strip().replace(' ', '_')
    return safe.lower() or "document"

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

        # --- SPHINX NEEDS LOGIC ---
        if 'sphinx_needs' in getattr(config, 'extensions', []):
            needs_props = [
                'title_font', 'title_font_size', 'title_color', 'title_background_color',
                'title_icon', 'title_icon_size', 'title_icon_color', 'title_icon_raise', 'title_vertical_position',
                'metadata_background_color', 'metadata_font', 'metadata_font_size', 'metadata_font_color',
                'metadata_key_font', 'metadata_key_color',
                'content_background_color', 'content_font', 'content_font_size', 'content_font_color',
                'segmentation_style'
            ]
            
            needs_defaults = {
                'title_font_size': r'\large\bfseries',
                'title_color': '#FFFFFF',
                'title_background_color': '#0092FA',
                'title_icon': '',
                'title_icon_size': '',
                'title_icon_color': '#FFFFFF',
                'title_icon_raise': '0pt',
                'metadata_background_color': '#E9ECEF',
                'metadata_font_size': r'\small',
                'metadata_font_color': '#495057',
                'metadata_key_color': '#212529',
                'content_background_color': '#FFFFFF',
                'content_font_size': r'\normalsize',
                'content_font_color': '#000000',
                'segmentation_style': 'solid'
            }

            for p in needs_props:
                val = getattr(config, f'docdash_needs_{p}', None)
                if val is None:
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
                        val = f"{val_str}, draw=ddneed@titlebg, line width=0.5pt"

                template_vars[f'docdash_needs_{p}'] = val
                
                # Pre-calculate CMYK for colors
                if p.endswith('_color'):
                    template_vars[f'docdash_needs_{p}_cmyk'] = hex_to_cmyk_string(val)

            # Auto-calculate vertical position using robust font-relative sizing (1em)
            v_pos = getattr(config, 'docdash_needs_title_vertical_position', None)
            manual_raise = getattr(config, 'docdash_needs_title_icon_raise', None)

            if v_pos == 'middle':
                template_vars['docdash_needs_title_icon_raise'] = r'\dimexpr 0.5\ht\strutbox - 0.5\height\relax'
            elif v_pos == 'top':
                template_vars['docdash_needs_title_icon_raise'] = r'\dimexpr 0.7em - \height\relax'
            elif v_pos == 'bottom':
                template_vars['docdash_needs_title_icon_raise'] = '0pt'
            else:
                template_vars['docdash_needs_title_icon_raise'] = manual_raise if manual_raise is not None else '0pt'

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
        
    from docutils import nodes
    
    for node in list(doctree.traverse(nodes.Element)):
        classes = node.get('classes', [])
        if 'need' not in classes and 'need_node' not in classes and node.tagname != 'need':
            continue
            
        if node.get('docdash_processed'):
            continue
        for child in node.traverse(nodes.Element):
            child['docdash_processed'] = True

        nid = node.attributes.get('ids', [None])[0]
        if not nid:
            for child in node.traverse(nodes.target):
                if child.get('ids'):
                    nid = child['ids'][0]
                    break
        if not nid:
            continue

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

        # Construct the new raw LaTeX wrapped tree
        wrapper = nodes.container(classes=['docdash-flat-need'])
        wrapper.append(nodes.raw('', f'\n\\begin{{docdashneedbox}}{{{title_str}}}\n', format='latex'))

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
        'content_font', 'content_font_color', 'content_font_size'
    ]

    for t in admon_types:
        for p in admon_props:
            app.add_config_value(f'docdash_admonition_{t}_{p}', None, 'env')

    # Sphinx Needs Customization Namespace
    needs_props = [
        'title_font', 'title_font_size', 'title_color', 'title_background_color',
        'title_icon', 'title_icon_size', 'title_icon_color', 'title_icon_raise', 'title_vertical_position',
        'metadata_background_color', 'metadata_font', 'metadata_font_size', 'metadata_font_color',
        'metadata_key_font', 'metadata_key_color',
        'content_background_color', 'content_font', 'content_font_size', 'content_font_color',
        'segmentation_style'
    ]
    for p in needs_props:
        app.add_config_value(f'docdash_needs_{p}', None, 'env')

    app.connect('config-inited', config_inited, priority=900)
    app.connect('build-finished', build_finished)
    
    # Run the AST Flattener securely at the very end of AST resolution
    app.connect('doctree-resolved', process_needs_ast, priority=999)
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }