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

```

**Note on LaTeX Engine:** This theme relies on `fontspec` and KOMA classes, which require LuaLaTeX. The extension will automatically set `latex_engine = 'lualatex'` if you haven't explicitly configured an engine. If you manually set it to something else (like `xelatex`), the build will proceed but generate a warning.

---

## Features & Customization

The theme provides sensible defaults, but you can easily override them using specific variables in your `conf.py`.

### 1. Dynamic File Generation

You **do not** need to specify `latex_documents` or `.xmpdata` files manually. The theme automatically generates the `.tex` and `.xmpdata` output names based on your `project` and `author` variables.

### 2. Custom Colors

You can customize the accent colors of your PDF using standard Hex codes. The theme will automatically convert these to the CMYK values required by LaTeX.

Add these variables to your `conf.py` to override the defaults:

```python
# --- Default Color Values ---
docdash_titlepagecolor = '#FF9900'       # The main color used on the title page
docdash_colorchapternumber = '#0092FA'   # The large chapter numbers
docdash_colorsectionnumber = '#D4D4D4'   # Section numbering
docdash_colorchapterline = None          # Optional. Defaults to a lighter shade of the chapter number color

```

### 3. Custom Fonts

The theme uses `fontspec` to define system fonts. You can easily swap these out in your `conf.py`.

> **Important:** Because LuaLaTeX compiles using system fonts, any font you specify here **must be installed on the operating system** running the Sphinx build.

```python
# --- Default Font Settings ---
docdash_main_font = 'Lato Light'
docdash_main_font_options = 'BoldFont={Lato Regular}, ItalicFont={Lato Light Italic}, BoldItalicFont={Lato Italic}'
docdash_sans_font = 'Exo 2'
docdash_mono_font = 'IosevkaTerm NF'

# Example override:
# docdash_main_font = 'Ubuntu'
# docdash_main_font_options = '' # Clear the Lato-specific overrides if your new font handles weights automatically

```

### 4. Margins & Layout

Override the default layout by defining `latex_elements` in your `conf.py`. Only the keys you define will be overridden; the rest of the theme defaults (like your custom colors and fonts) will remain intact.

```python
latex_elements = {
    # Example: Changing the margins
    'sphinxsetup': 'hmargin={1.5cm,2.5cm}, vmargin={2cm,2cm}, marginpar=2.5cm'
}

```

### 5. Logos & Standard Sphinx Options

If you specify a logo, the theme will automatically handle adding it to the required LaTeX files:

```python
latex_logo = '_static/my-custom-logo.png'

```

Standard Sphinx LaTeX options remain fully configurable by the user, for example:

```python
latex_appendices = ['glossary', 'appendices', 'references']

```

---

## Requirements

* A full `texlive` installation is expected in the build environment.
* The system building the documentation must have the specified fonts installed natively.
