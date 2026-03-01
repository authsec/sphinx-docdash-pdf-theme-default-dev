import os
import re
from pathlib import Path
from sphinx.util import logging

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

def get_safe_filename(name: str) -> str:
    """Creates a filesystem-safe string from a project name."""
    safe = re.sub(r'[^A-Za-z0-9\s]+', '', name).strip().replace(' ', '_')
    return safe.lower() or "document"

def config_inited(app, config):
    """Fired when Sphinx finishes reading conf.py."""
    
    # 1. Smart default for latex_engine
    # 'pdflatex' is the base Sphinx default. If it's still 'pdflatex', the user likely didn't set it.
    if config.latex_engine == 'pdflatex':
        config.latex_engine = 'lualatex'
    # If it's not lualatex (and not pdflatex), the user explicitly chose something else (e.g., 'xelatex').
    elif config.latex_engine != 'lualatex':
        logger.warning(
            f"[DocDash PDF Theme] The latex_engine is set to '{config.latex_engine}'. "
            "This theme is designed for 'lualatex' to support KOMA classes and custom fonts. "
            "Your build might not render correctly."
        )

    # 2. Set default document class to KOMA (scrbook)
    if not config.latex_docclass:
         config.latex_docclass = {'manual': 'scrbook'}
    else:
         config.latex_docclass.setdefault('manual', 'scrbook')

    # 3. Dynamic LaTeX document naming
    safe_project = get_safe_filename(config.project)
    # If the user hasn't modified latex_documents from the basic Sphinx default, override it:
    if not config.latex_documents or 'outpdfname.tex' in config.latex_documents[0][1]:
        config.latex_documents = [
            (config.root_doc, f"{safe_project}.tex", config.project, config.author, 'manual'),
        ]

    # 4. Read Preamble from package
    pkg_dir = Path(__file__).parent.resolve()
    preamble_path = pkg_dir / "preamble.tex"
    my_preamble = preamble_path.read_text(encoding="utf-8") if preamble_path.exists() else ""

    # 5. Define Defaults (only applies if the user hasn't overridden them)
    default_elements = {
        'fncychap': '',
        'tableofcontents': '\\tableofcontents',
        'sphinxsetup': 'hmargin={1.5cm,2.5cm}, vmargin={2cm,2cm}, marginpar=2.5cm',
        'preamble': my_preamble,
        'papersize': 'a4paper',
        'pointsize': '11pt',
        'extraclassoptions': 'openright,twoside,parskip=half,numbers=noenddot',
        'fontpkg': r'''
\makeatletter
\AddToHook{package/capt-of/before}{\let\captionof\undefined}
\providecommand{\py@HeaderFamily}{\sffamily\bfseries}
\makeatother

\usepackage{fontspec}
\setmainfont{Lato Light}[
    BoldFont={Lato Regular},
    ItalicFont={Lato Light Italic},
    BoldItalicFont={Lato Italic}
]
\setsansfont{Exo 2}
\setmonofont{IosevkaTerm NF}
'''
    }

    # Inject defaults without overwriting user configs
    for key, value in default_elements.items():
        if key not in config.latex_elements:
            config.latex_elements[key] = value

    # 6. Logo and Additional Files Handling
    # Add logo if specified
    if config.latex_logo and config.latex_logo not in config.latex_additional_files:
        config.latex_additional_files.append(config.latex_logo)

    # Auto-inject the required empty style files
    sty_dir = pkg_dir / "latex_styles"
    config.latex_additional_files.extend([
        str(sty_dir / "sphinxlatexstyleheadings.sty"),
        str(sty_dir / "sphinxlatexstylepage.sty")
    ])

def build_finished(app, exception):
    """Fired when the Sphinx build is complete."""
    if exception is not None or app.builder.name != 'latex':
        return
    
    # Generate the XMP metadata file dynamically in the output directory
    safe_project = get_safe_filename(app.config.project)
    
    # We populate tags dynamically using Sphinx's config context
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
    # Priority 900 ensures this runs after most extensions but before core LaTeX builder initialization
    app.connect('config-inited', config_inited, priority=900)
    app.connect('build-finished', build_finished)
    
    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }