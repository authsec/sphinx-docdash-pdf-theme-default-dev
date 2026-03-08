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

**Note on LaTeX Engine:** This theme relies on `fontspec` and KOMA classes, which require LuaLaTeX. The extension will automatically set `latex_engine = 'lualatex'` if you haven't explicitly configured an engine.

---

## Features & Customization

The theme acts as a clean, minimalist canvas out of the box. **It applies zero colors or custom sizes unless you explicitly define them.** If an option is omitted from your configuration, the logic is seamlessly disabled, leaving you with standard KOMA-Script defaults.

All options are properly namespaced under `docdash_`.

### 1. The Classic "DocDash Look"

If you want to instantly replicate the iconic orange and blue DocDash styling, simply copy and paste these defaults into your `conf.py`:

```python
docdash_title_page_color = '#FF9900'
docdash_chapter_number_color = '#0092FA'
docdash_chapter_number_size = r'\fontsize{30pt}{30pt}\selectfont'
docdash_section_number_color = '#D4D4D4'
docdash_subsection_number_color = '#D4D4D4'
docdash_subsubsection_number_color = '#D4D4D4'

```

### 2. Document Inheritance Hierarchy

The theme is capable of inheriting font, size, and color properties top-down through the document hierarchy (`part` -> `chapter` -> `section` -> `subsection` -> `subsubsection`). If you assign a font or color to your parts, all sub-sections will automatically inherit that styling unless you explicitly override them.

```python
docdash_inherit_all = True    # Global kill-switch for inheritance
docdash_inherit_font = True   # Automatically inherit font families downward
docdash_inherit_color = True  # Automatically inherit hex colors downward
docdash_inherit_size = False  # By default, we let KOMA natively handle font scaling.

```

### 3. Universal Element Namespacing

You can precisely control the **color** (via Hex codes), **font** (via system font names), and **size** (via raw LaTeX string injections) of every major document element.

> **Crucial Tip on Sizes & Spacing:** > When passing LaTeX commands to the `_size` variable, you must use Python "raw strings" (prefixing with an `r`) so the `\` is not interpreted as an escape character!
> You can use standard relative sizes (like `r'\huge'` or `r'\normalsize'`), or exact point sizes using `r'\fontsize{32pt}{36pt}\selectfont'`.
> The `\fontsize{}{}` command takes two parameters:
> 1. **Font Size (e.g., `32pt`):** How large the text characters are.
> 2. **Line Spacing / Baselineskip (e.g., `36pt`):** The vertical distance from the bottom of this line to the bottom of the next line below it.
> 
> 
> *Design Hack:* If your subtitle feels too far away from your main title, you can artificially shrink the line spacing parameter on your main title to pull the subtitle upward! (e.g., `docdash_title_size = r'\fontsize{32pt}{14pt}\selectfont'`).

```python
# --- Universal DocDash Theme Overrides ---

# Titles & Metadata
docdash_title_font = 'Ubuntu'
docdash_title_color = '#E63946'
docdash_title_size = r'\fontsize{32pt}{36pt}\selectfont'

docdash_subtitle = "My Document Subtitle"
# docdash_subtitle_font = ...
# docdash_subtitle_color = ...
# docdash_subtitle_size = ...

# docdash_author_font = ...
# docdash_author_color = ...
# docdash_author_size = ...

docdash_show_release = False # Swallows the Release/Version string strictly for PDF Output
# docdash_release_version_font = ...
# docdash_release_version_color = ...
# docdash_release_version_size = ...

# docdash_date_font = ...
# docdash_date_color = ...
# docdash_date_size = ...

# Document Structure Text
docdash_part_font = 'Ewert'
docdash_part_color = '#008734'
# docdash_part_size = ...

# docdash_chapter_font = ... (Inherits 'Ewert')
# docdash_chapter_color = ... (Inherits '#008734')
# docdash_chapter_size = ...

# docdash_section_font = ... (Inherits 'Ewert')
# docdash_section_color = ... (Inherits '#008734')
# docdash_section_size = ...

# Document Structure Numbers
# The Part number layout ("Part I") can optionally be split into two pieces for complex font combinations:
docdash_part_number_part_font = 'Kaushan Script'
docdash_part_number_part_color = '#00FF11'
docdash_part_number_part_size = r'\fontsize{32pt}{36pt}\selectfont'

docdash_part_number_number_font = 'Oi'
docdash_part_number_number_color = '#FFBB00'
docdash_part_number_number_size = r'\fontsize{32pt}{36pt}\selectfont'

# If left blank, they automatically fallback to these singular part_number values:
# docdash_part_number_font = 'Kapakana'
# docdash_part_number_color = '#00FF11'

# Sphinx Specifics
# docdash_rubric_font = ...
docdash_rubric_color = '#A8DADC'
# docdash_rubric_size = ...

```

### 4. Core Theme Fonts

You can modify the overarching fallback fonts.

```python
# --- Default Font Settings ---
docdash_main_font = 'Lato Light'
docdash_main_font_options = 'BoldFont={Lato Regular}, ItalicFont={Lato Light Italic}, BoldItalicFont={Lato Italic}'
docdash_sans_font = 'Exo 2'
docdash_mono_font = 'IosevkaTerm NF'

```

> **Important:** Because LuaLaTeX compiles using system fonts, any font you specify here **must be installed on the operating system** running the Sphinx build.

