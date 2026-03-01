# Sphinx DocDash PDF Theme Default

The default PDF theme designed for the DocDash document authoring system. It provides a clean, professional LaTeX/PDF layout utilizing KOMA classes and LuaLaTeX.

## Installation

Install via pip:

```bash
pip install sphinx-docdash-pdf-theme-default

```

## Usage

In your Sphinx `conf.py` file, add the theme to your extensions list:

```python
extensions = [
    # ... other extensions
    'docdash_pdf_theme',
]

# Required: The theme relies on LuaLaTeX and KOMA classes.
latex_engine = 'lualatex'

```

### Dynamic File Generation

You **do not** need to specify `latex_documents` or `.xmpdata` files manually. The theme automatically generates the `.tex` and `.xmpdata` output names based on your `project` and `author` variables in `conf.py`.

### Customization

The theme provides sensible defaults, but you can easily override them using standard Sphinx configuration options.

#### Changing Margins & Layout

Override the default layout by defining `latex_elements` in your `conf.py`. Only the keys you define will be overridden; the rest of the theme defaults (like fonts) will remain intact.

```python
latex_elements = {
    # Example: Changing the margins
    'sphinxsetup': 'hmargin={1.5cm,2.5cm}, vmargin={2cm,2cm}, marginpar=2.5cm'
}

```

#### Logos

If you specify a logo, the theme will automatically handle adding it to the required LaTeX files:

```python
latex_logo = '_static/my-custom-logo.png'

```

#### Appendices & References

Standard Sphinx LaTeX options remain fully configurable by the user:

```python
latex_appendices = ['glossary', 'appendices', 'references']

```

## Requirements

* A full `texlive` installation is expected in the build environment.
* `lualatex` must be the designated build engine. The extension will generate a warning during the build process if another engine is detected.
