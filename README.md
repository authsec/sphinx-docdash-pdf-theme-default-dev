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

### 1. Structural Layout Settings

By default, the theme pushes chapter and section numbers into the page margins and *alternates* their placement based on the page number (right margin on right pages, left margin on left pages).

You can strictly configure this alignment, margin placement, the spacing gap, and even toggle a decorative colored structural line, **on a per-element basis!**

```python
# --- Alignment ---

docdash_heading_align = 'alternate'  # 'alternate', 'left', 'right'

# docdash_chapter_align = 'right'    # Override lock just for Chapters

# --- Margin Logic ---

docdash_numbers_in_margin = True     # Global toggle

# docdash_section_number_margin = False # Specific override: pushes Section numbers inline

# --- Margin Spacing ---

# Controls the physical empty space between the edge of the margin number and the start of the title block.

docdash_heading_margin_space = '1.5em' # Global default applied to ALL headings

# docdash_section_margin_space = '0.5em' # Specific override applied ONLY to sections!

# --- Decorative Lines ---

# Automatically draws a colored bar next to the number if placed in the margin.

# docdash_chapter_number_line = True   # Chapters have it on by default

# docdash_section_number_line = True   # Sections have it off by default

# docdash_section_line_height = '2cm'  # Defaults to '10cm'

# docdash_section_line_color = '#FF0000' # Defaults to inheriting the number's color

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

```python
# --- Universal DocDash Theme Overrides ---

docdash_title_page_color = '#FF9900' # Paints the cover page background

# Titles & Metadata
docdash_title_font = 'Ubuntu'
docdash_title_color = '#E63946'
docdash_title_size = r'\fontsize{32pt}{36pt}\selectfont'

docdash_subtitle = "My Document Subtitle"
# docdash_subtitle_font = ...

docdash_show_release = False # Swallows the Release/Version string strictly for PDF Output

# Document Structure Text
docdash_part_font = 'Ewert'
docdash_part_color = '#008734'
# docdash_chapter_font = ... (Inherits 'Ewert')

# Document Structure Numbers
# The Part number layout ("Part I") can optionally be split into two pieces for complex font combinations:
docdash_part_number_part_font = 'Kaushan Script'
docdash_part_number_part_color = '#00FF11'

docdash_part_number_number_font = 'Oi'
docdash_part_number_number_color = '#FFBB00'

docdash_chapter_number_color = ""  # Clears the built-in blue default to inherit #00FF11 from part!
docdash_section_number_color = ""  # Clears the built-in gray default

# Content Styling
docdash_needs_content_font = 'Stardos Stencil'
docdash_needs_content_font_size = r'\fontsize{9pt}{9pt}\selectfont'
docdash_needs_content_font_color = '#FFFFFF'

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
