# DocDash PDF Theme - Developer Guide (AGENTS.md)

> **Purpose:** This file orients the developer (or AI agent) to the `docdash_pdf_theme` project — a Sphinx extension that produces professional PDF output via LuaLaTeX/KOMA-Script/tcolorbox. It documents the architecture, the core/theme relationship, all available customization knobs, and the development workflow.

---

## 1. Project Overview

This project is the **default PDF theme** for the DocDash document authoring system. It is a **Sphinx extension** that hooks into Sphinx's LaTeX writer to transform RST documents into beautifully styled PDFs.

### Key Technologies
- **Sphinx** (>=5.0) — Documentation framework
- **LuaLaTeX** — Required LaTeX engine (fontspec + KOMA-Script)
- **KOMA-Script** (`scrbook` class) — Document structure
- **tcolorbox** — Colored boxes for admonitions, containers, needs
- **TikZ** — Underlay decorations, part backgrounds, draft watermarks
- **Jinja2** — Template engine for preamble.tex_t

### Relationship to Core
```
docdash-pdf-theme-core-dev/    ← The CORE (shared library)
    docdash_pdf_theme_core/    ← Provides:
        - Three-tier merge architecture
        - Config manifest (CORE_CONFIG_MANIFEST)
        - Absolute fallback styles
        - Style path resolution engine
        - AST processors (containers, needs, epigraphs, tables, code)

docdash_pdf_theme/             ← This THEME (builds on core)
    docdash_pdf_theme/         ← Our extension package
        __init__.py            ← Sphinx extension entry point
        utils.py               ← Color utilities (ported from core)
        default_config.py      ← Theme-specific default dictionaries
        preamble.tex_t         ← Main LaTeX preamble template
        latex_styles/          ← Custom .tex_t style overrides
            admonition/        ← Custom admonition box styles
            container_title_style/ ← Container title geometry styles
            need/              ← Sphinx-Needs box styles
            title_page/        ← Cover page templates
            sphinxlatexstyle*.sty ← KOMA heading & page style overrides
```

**Important:** This theme is a **standalone** package that does NOT import from `docdash_pdf_theme_core`. It ports the core's utilities (`utils.py`) and default configs (`default_config.py`) directly into the theme. The core and theme are parallel projects in the same monorepo.

---

## 2. Directory Structure

```
docdash_pdf_theme/
├── __init__.py                  # Entry point: config_inited, setup, AST processors
├── utils.py                     # Color conversion utilities
│   ├── get_safe_filename()      # Sanitize project names for LaTeX
│   ├── adjust_hex_brightness()  # Lighten/darken hex colors
│   ├── get_highest_contrast_color()  # WCAG 2.0 contrast compliance
│   └── hex_to_cmyk_string()    # Hex → LaTeX CMYK conversion
├── default_config.py            # Default dictionaries for needs & admonitions
├── preamble.tex_t               # Main LaTeX preamble (Jinja2 template)
└── latex_styles/
    ├── sphinxlatexstyleheadings.sty   # KOMA heading style overrides
    ├── sphinxlatexstylepage.sty       # Page layout style overrides
    ├── admonition/
    │   ├── default.tex_t      # "default" admonition style (boxed title with icon)
    │   └── note.tex_t         # "note" admonition style (plain box with inline title)
    ├── container_title_style/
    │   ├── classic.tex_t      # Simple left-aligned title box
    │   ├── floating.tex_t     # Chevron/arrow-shaped title background
    │   └── ribbon.tex_t       # 3D ribbon-style title bar
    ├── need/
    │   └── default.tex_t      # Sphinx-Needs tcolorbox template
    └── title_page/
        └── default.tex_t      # Cover page background injection
```

---

## 3. Architecture

### 3.1 Sphinx Extension Lifecycle

The extension hooks into Sphinx at four key points:

1. **`setup(app)`** — Registers config values, custom directive (`stylebox`), and connects event handlers.
2. **`config_inited(app, config)`** (priority=900) — The **main engine**. Runs when Sphinx finishes reading `conf.py`. Translates Python dicts → flat Jinja variables → renders `preamble.tex_t` → injects into `latex_elements['preamble']`.
3. **`doctree-resolved`** handlers (priority=995-999) — AST processors that transform RST nodes into raw LaTeX:
   - `process_containers_ast` (998) — `.. container::` → `ddcontainer{...}`
   - `process_epigraph_ast` (997) — `.. epigraph::` → KOMA `\dictum{}`
   - `process_needs_ast` (999) — Sphinx-Needs nodes → `docdashneedboxrouter`
4. **`build_finished(app, exception)`** — Writes XMP metadata file.

### 3.2 Configuration Resolution: Three-Tier Merge

All configuration dictionaries follow a **three-tier merge** pattern. The order of precedence (lowest to highest):

```
Core Defaults → Theme Defaults → User Config (conf.py)
```

For each category (title_page, headings, parts, etc.):
```python
resolved = deep_update(
    deep_update(core_defaults.copy(), theme_defaults.copy()),
    user_config.copy()
)
```

### 3.3 Style Resolution Engine

For `.tex_t` style files (admonitions, containers, needs, title pages), the theme uses an **aggressive path hunting** system:

1. User's `docdash_{style}_style_path` custom folder
2. User's `{confdir}/{srcdir}/{custom_path}/{style_name}.tex_t`
3. User's `{confdir}/{srcdir}/{style_name}.tex_t`
4. User's `{confdir}/{srcdir}/{style_name}.tex`
5. Theme's `latex_styles/{category}/{style_name}.tex_t`

If no file is found, it falls back to the theme's `default.tex_t` in that category.

### 3.4 Jinja2 Template Delimiters

The template engine uses **LaTeX-safe delimiters** to avoid conflicts with `{%}`:

| Delimiter | Start | End |
|-----------|-------|-----|
| Blocks | `<%` | `%>` |
| Variables | `<<` | `>>` |
| Comments | `<#` | `#>` |

---

## 4. All Customization Knobs

### 4.1 Global Settings (flat config values)

| Config Value | Type | Default | Description |
|-------------|------|---------|-------------|
| `docdash_title_page_top_line` | bool | `False` | Show/hide top rule on title page |
| `docdash_footer_logo` | str | `None` | Path to footer logo image |
| `docdash_footer_logo_height` | str | `'1.5em'` | Height of footer logo |
| `docdash_headsep` | str | `'8mm'` | Header-to-text distance |
| `docdash_footskip` | str | `'10mm'` | Text-to-footer distance |
| `docdash_headheight` | str | `'18pt'` | Header block height |
| `docdash_footheight` | str | `'25pt'` | Footer block height |
| `docdash_show_release` | bool | `True` | Show/hide version on title page |
| `docdash_main_font` | str | `'Lato Light'` | Main/serif font |
| `docdash_main_font_options` | str | `'BoldFont={...}, ItalicFont={...}'` | fontspec options |
| `docdash_sans_font` | str | `'Exo 2'` | Sans-serif font |
| `docdash_mono_font` | str | `'IosevkaTerm NF'` | Monospace/font |
| `docdash_inherit_all` | bool | `True` | Global inheritance toggle |
| `docdash_inherit_font` | bool | `True` | Inherit fonts down hierarchy |
| `docdash_inherit_color` | bool | `True` | Inherit colors down hierarchy |
| `docdash_inherit_size` | bool | `False` | Inherit sizes down hierarchy |

### 4.2 Dictionary Configs (nested dicts)

#### `docdash_title_page` — Cover Page

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `subtitle` | str | `None` | Subtitle text |
| `page_color` | str (hex) | `None` | Solid background color |
| `background_image` | str (path) | `None` | Full-page background image |
| `background_image_mode` | str | `'fit'` | `'fit'`, `'stretch'`, `'tile'` |
| `background_image_align` | str | `'center'` | Image alignment |
| `background_image_keepaspectratio` | bool | `False` | Preserve aspect ratio |
| `color_opacity` | str | `'0.5'` (with image) / `'1.0'` (without) | Color overlay opacity |
| `top_line` | bool | `False` | Show top rule |
| `template` | str | `'default'` | Which title_page template to use |
| `title_font` / `title_size` / `title_color` | str | — | Title styling |
| `subtitle_font` / `subtitle_size` / `subtitle_color` | str | — | Subtitle styling |
| `author_font` / `author_size` / `author_color` | str | — | Author styling |
| `date_font` / `date_size` / `date_color` | str | — | Date styling |
| `release_version_font` / `release_version_size` / `release_version_color` | str | — | Version styling |

#### `docdash_headings` — Chapter/Section/Margin Layout

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `align` | str | `'alternate'` | `'alternate'`, `'left'`, `'right'`, `'center'` |
| `numbers_in_margin` | bool | `True` | Push numbers into margin |
| `margin_space` | str | `'1.5em'` | Gap between number and text |
| `chapter.align` | str | inherits | Per-chapter alignment override |
| `chapter.number_margin` | bool | inherits | Per-chapter margin toggle |
| `chapter.number_line` | bool | `True` | Show decorative line (default for chapters) |
| `chapter.line_height` | str | `'10cm'` | Length of decorative line |
| `chapter.margin_space` | str | inherits | Per-chapter margin gap |
| `chapter.font` / `chapter.size` / `chapter.color` | str | — | Chapter text styling |
| `chapter.number_font` / `chapter.number_size` / `chapter.number_color` | str | — | Chapter number styling |
| `chapter.line_color` | str | inherits | Decorative line color |
| `section` / `subsection` / `subsubsection` | dict | — | Same keys as chapter |

#### `docdash_parts` — Part Pages (with per-part backgrounds)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `font` / `size` / `color` | str | — | Global part text styling |
| `part_number_font` / `part_number_size` / `part_number_color` | str | — | "Part" text styling |
| `part_number_part_font` / `part_number_part_color` | str | — | "Part" word styling (split) |
| `part_number_number_font` / `part_number_number_color` | str | — | Number styling (split) |
| `1: {image, background_color, ...}` | dict | — | Per-part overrides by index |
| `1.image` | str (path) | — | Full-page background image for Part 1 |
| `1.background_color` / `1.color` | str (hex) | — | Color overlay (supports 8-digit alpha) |
| `1.font_color` / `1.font` / `1.size` | str | — | Part text overrides |
| `1.number_color` / `1.number_font` / `1.number_size` | str | — | Number overrides |
| `1.epigraph_color` / `1.epigraph_author_color` | str | — | Epigraph color overrides |
| `1.appendix` | bool | `False` | If True, switches to letter-based numbering |

#### `docdash_epigraphs` — Quote/Dictum Styling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `width` | str | `'0.5\\textwidth'` | Quote box width |
| `format` | str | `'--- #1'` | Author format (#1 = author name) |
| `align_box` | str | `'right'` | Box alignment: `'left'`, `'center'`, `'right'` |
| `align_text` | str | `'left'` | Text alignment inside box |
| `align_author` | str | `'right'` | Author alignment inside box |
| `font` / `size` / `color` | str | — | Quote text styling |
| `author_font` / `author_size` / `author_color` | str | — | Author text styling |
| `part` / `chapter` / `section` / `subsection` / `subsubsection` | dict | — | Level-specific overrides |

#### `docdash_draft` — Draft Watermark

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `text` | str | `None` | **Set to activate** watermark. Supports `{date}`, `{ext_version}`, `{project_version}` |
| `date_format` | str | `'%Y-%m-%d %H:%M:%S'` | Python strftime format |
| `timezone` | str | `'local'` | `'local'`, `'UTC'`, `'Europe/Berlin'` |
| `color` | str (hex) | `'#00000044'` | Color (8-digit hex for alpha) |
| `font` | str | `None` | Custom font |
| `font_size` | str | `r'\Huge\bfseries\sffamily'` | Font size |

#### `docdash_admonitions` — Admonition Boxes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `generic.style` | str | `'default'` | Which .tex_t to use |
| `generic.title_icon` | str | `r'\textbf{i}'` | Icon (LaTeX or image path) |
| `generic.title_icon_color` | str | `'#FFFFFF'` | Icon color |
| `generic.title_icon_size` | str | `''` | Icon size override |
| `generic.title_icon_padding` | str | `'3ex'` | Icon box width |
| `generic.title_decoration_spacing` | str | `'2mm'` | Right decoration spacing |
| `generic.title_background_color` | str | `'#0092FA'` | Title bar background |
| `generic.title_icon_box_background_color` | str | `'#0092FA'` | Icon box background |
| `generic.title_font_color` | str | `'#FFFFFF'` | Title text color |
| `generic.title_font_size` | str | `r'\large\bfseries'` | Title font size |
| `generic.title_font` | str | `''` | Custom title font |
| `generic.content_background_color` | str | `'#F8F9FA'` | Body background |
| `generic.content_background_color_nested` | str | `'#FFFFFF'` | Alternating nested color |
| `generic.content_font_color` | str | `'#000000'` | Body text color |
| `generic.content_font_size` | str | `r'\normalsize'` | Body font size |
| `generic.content_font` | str | `''` | Custom body font |
| `generic.before_skip` / `generic.after_skip` | str | — | Vertical spacing |
| `note` / `warning` / `hint` / `danger` / `error` / `caution` / `tip` / `important` / `attention` | dict | — | Type-specific overrides |
| `note.style` | str | `'default'` | Override structure for this type |

#### `docdash_needs` — Sphinx-Needs Styling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `generic.style` | str | `'default'` | Which .tex_t to use |
| `generic.title_font` / `title_font_size` / `title_color` | str | — | Title bar styling |
| `generic.title_background_color` | str | `'#0092FA'` | Title background |
| `generic.title_icon` | str | `''` | Icon (LaTeX or image) |
| `generic.title_icon_size` / `title_icon_color` | str | — | Icon sizing/color |
| `generic.title_icon_raise` | str | `'0pt'` | Manual icon vertical shift |
| `generic.title_icon_raise_offset` | str | `'0pt'` | Additional icon offset |
| `generic.title_vertical_position` | str | `''` | `'top'`, `'middle'`, `'bottom'` |
| `generic.segmentation_style` | str | `'solid'` | `'solid'`, `'dashed'`, `'dotted'`, `'dashdotted'`, `'none'` |
| `generic.segmentation_color` | str | inherits from title_bg | Segmentation line color |
| `generic.metadata_background_color` | str | `'#E9ECEF'` | Metadata section bg |
| `generic.metadata_font` / `metadata_font_size` / `metadata_font_color` | str | — | Metadata text styling |
| `generic.metadata_key_font` / `metadata_key_color` / `metadata_key_font_size` | str | — | Key column styling |
| `generic.content_background_color` / `content_font` / `content_font_size` / `content_font_color` | str | — | Content body styling |
| `generic.before_skip` / `generic.after_skip` | str | — | Vertical spacing |
| `req` / `spec` / etc. | dict | — | Per-type overrides |

#### `docdash_containers` — Custom `.. container::` Boxes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `my_container.style` | str | `'default'` | Body .tex_t template |
| `my_container.title_style` | str | `'classic'` | Title geometry .tex_t |
| `my_container.container_frame` | bool | `True` | Draw outer border |
| `my_container.match_text_width` | bool | `False` | Align with body text |
| `my_container.title_icon` | str | `''` | Icon before title |
| `my_container.title_font` / `title_font_size` | str | — | Title text styling |
| `my_container.title_color` | str | `'#1E3A8A'` | Primary color (frame + title bg) |
| `my_container.title_font_color` | str | auto | Title text color |
| `my_container.title_icon_color` | str | inherits | Icon color |
| `my_container.title_icon_font_size` | str | `''` | Icon size override |
| `my_container.content_font` / `content_font_size` / `content_font_color` / `content_background_color` | str | — | Body styling |

### 4.4 Custom Folder Paths

| Config Value | Default | Description |
|-------------|---------|-------------|
| `docdash_container_title_style_path` | `''` | Custom path for container title .tex_t files |
| `docdash_admonition_style_path` | `''` | Custom path for admonition .tex_t files |
| `docdash_need_style_path` | `''` | Custom path for needs .tex_t files |
| `docdash_title_page_template_path` | `''` | Custom path for title page .tex_t files |

---

## 5. Template Files Reference

### 5.1 `preamble.tex_t` — Main Preamble Template

This is the **single largest file** in the theme. It generates all LaTeX code for:

1. **Package imports** — calc, pdflscape, scrlayer-scrpage, tikz, tcolorbox, varwidth, xpatch
2. **Document geometry** — headsep, footskip, headheight, footheight
3. **Page style** — scrheadings with chapter mark in header, page number in footer, optional logo in footer
4. **Draft watermark** — TikZ-based rotated text watermark (left on odd pages, right on even)
5. **Epigraph/Dictum** — KOMA dictum configuration per level, setup macro for dynamic switching
6. **Title page injection** — Calls `<< docdash_rendered_title_page >>`
7. **Part backgrounds** — Per-part color/image overlays via TikZ
8. **Part number formatting** — Split partnumber (e.g., "Part" + "1" in different fonts)
9. **Universal color definitions** — All element colors defined as CMYK
10. **KOMA font injection** — `addtokomafont` for title, subtitle, author, date, releaseversion, chapter, section, subsection, subsubsection, chapternumber, sectionnumber, subsectionnumber, subsubsectionnumber
11. **Rubric command override** — Custom `\sphinxrubric` if styling defined
12. **Title/Author/Date/Release macro hooks** — Force KOMA fonts on Sphinx macros
13. **Part format override** — Split `partformat` for partnumberpart + partnumbernumber
14. **Heading alignment** — Dynamic margin/inline layout with decorative lines
15. **Menu selection arrow fix** — Handles Unicode ‣ → \rightarrow
16. **Admonition router** — Color/font definitions + loaded styles + dynamic `sphinxadmonition` redefinition
17. **Container styles** — Loaded title styles + container tcolorbox definitions
18. **Sphinx-Needs router** — Conditional (only if `sphinx_needs` in extensions)

### 5.2 `latex_styles/admonition/default.tex_t`

The **default admonition style** — a tcolorbox with:
- Boxed title attached to top-left
- Icon box with rounded corners
- Decorative `>>>` lines on the right
- Left and bottom colored borders
- Alternating background for nested boxes
- Corner accent line on south-east

### 5.3 `latex_styles/admonition/note.tex_t`

The **note admonition style** — a simpler style with:
- Full rounded box with colored border
- Title inline (not boxed) with icon
- No decorative right-side lines
- Clean, minimal appearance

### 5.4 `latex_styles/container_title_style/`

| File | Description |
|------|-------------|
| `classic.tex_t` | Simple left-aligned title in a colored box. Takes one argument (the primary color). |
| `floating.tex_t` | Chevron/arrow-shaped title background. Fills a triangle from title to frame edge. |
| `ribbon.tex_t` | 3D ribbon-style title bar with gradient and rounded top corners. |

### 5.5 `latex_styles/need/default.tex_t`

Sphinx-Needs tcolorbox with:
- Enhanced skin, breakable
- Colored frame matching title background
- Segmentation line separating metadata from content
- Metadata section with lighter background
- Icon + title in title bar
- Lower section (content) with different background

### 5.6 `latex_styles/title_page/default.tex_t`

Cover page background injection:
- Patches `\sphinxmaketitle` to add background
- Removes top rule if `top_line=False`
- Supports solid color or full-page image with opacity overlay

### 5.7 `latex_styles/sphinxlatexstyleheadings.sty`

KOMA-Script heading style overrides (loaded as additional file).

### 5.8 `latex_styles/sphinxlatexstylepage.sty`

Page layout style overrides (loaded as additional file).

---

## 6. Key Functions & Utilities

### 6.1 `utils.py`

| Function | Purpose |
|----------|---------|
| `get_safe_filename(name)` | Sanitize strings for LaTeX filenames (alphanumeric + underscores) |
| `adjust_hex_brightness(hex_color, percentage)` | Lighten (+) or darken (-) a hex color. Supports 3/4/6/8-char hex with alpha preservation |
| `get_highest_contrast_color(fg, bg, target='foreground', adjust_percent=0.0)` | Ensure WCAG 2.0 4.5:1 contrast ratio. Iteratively shifts color toward black/white |
| `hex_to_cmyk_string(hex_color)` | Convert hex → LaTeX CMYK string (e.g., `0.000, 0.000, 0.000, 1.000`) |

### 6.2 `default_config.py`

| Constant | Purpose |
|----------|---------|
| `DEFAULT_NEEDS_CONFIG` | Default dictionary for `docdash_needs['generic']` |
| `DEFAULT_ADMONITION_CONFIG` | Default dictionary for `docdash_admonitions['generic']` |

### 6.3 `__init__.py` Key Functions

| Function | Priority | Purpose |
|----------|----------|---------|
| `config_inited(app, config)` | 900 | Main engine: translates config → template vars → renders preamble |
| `process_containers_ast(app, doctree, docname)` | 998 | Wraps `.. container::` nodes in `ddcontainer{...}` environments |
| `process_epigraph_ast(app, doctree, docname)` | 997 | Converts `.. epigraph::` to KOMA `\dictum{}` with dynamic styling |
| `process_needs_ast(app, doctree, docname)` | 999 | Flattens Sphinx-Needs AST into `docdashneedboxrouter` environments |
| `build_finished(app, exception)` | — | Writes XMP metadata (.xmpdata file) |
| `StyleBoxDirective.run()` | — | Custom `.. stylebox::` directive for containers |

---

## 7. Development Workflow

### Adding a New Feature

1. **Determine if it's core or theme:**
   - If it's a general feature (new style type, new config option) → add to `docdash-pdf-theme-core-dev`
   - If it's a theme-specific style → add to `docdash_pdf_theme/latex_styles/`

2. **For theme changes:**
   - Add config values in `setup()` via `app.add_config_value()`
   - Process config in `config_inited()` → add to `template_vars`
   - Update `preamble.tex_t` to use new variables
   - Update `default_config.py` if adding new default dictionaries
   - Update this AGENTS.md

3. **For new `.tex_t` styles:**
   - Create file in appropriate `latex_styles/{category}/` folder
   - Use `<< variable >>` for Jinja2 interpolation
   - Use `<% if %>` / `<% for %>` / `<% set %>` for logic
   - Reference `template_vars` keys from `config_inited()`

### Testing

```bash
# Install the theme
pip install -e .

# Build a test document
cd docs_test/
sphinx-build -b latex . _build/latex

# Compile PDF
cd _build/latex
latexmk -lualatex yourfile.tex
```

### Key Files to Edit

| Goal | File(s) to Edit |
|------|-----------------|
| Add new config option | `__init__.py` (setup + config_inited) |
| Change a default value | `default_config.py` |
| Modify LaTeX output | `preamble.tex_t` |
| Add new visual style | `latex_styles/{category}/{name}.tex_t` |
| Change color utility | `utils.py` |
| Update package metadata | `pyproject.toml` |

---

## 8. Important Patterns & Gotchas

### 8.1 CMYK Color Conversion

All colors are converted to CMYK for LaTeX. The `hex_to_cmyk_string()` function handles:
- 3-char hex (`#FFF` → `#FFFFFF`)
- 4-char hex (`#FFFF` → `#FFFFFFFF`)
- 6-char hex (`#FFFFFF`)
- 8-char hex with alpha (alpha is **dropped** — CMYK doesn't support alpha)

### 8.2 Raw Strings for LaTeX

When passing LaTeX commands from Python, **always use raw strings** (`r'...'`):
```python
docdash_title_size = r'\fontsize{32pt}{36pt}\selectfont'  # Correct
docdash_title_size = '\fontsize{32pt}{36pt}\selectfont'    # WRONG - \f is not a valid escape
```

### 8.3 Jinja2 in LaTeX

Remember the delimiter differences:
- `{% if %}` → `<% if %>`
- `{{ variable }}` → `<< variable >>`
- `{# comment #}` → `<# comment #>`

### 8.4 Style Resolution Order

When a user requests a custom style (e.g., `title_style: 'my_custom'`):
1. Check custom path (`docdash_container_title_style_path`)
2. Check confdir/srcdir for `{style}.tex_t`
3. Check confdir/srcdir for `{style}.tex`
4. Check theme's `latex_styles/container_title_style/{style}.tex_t`
5. Fall back to theme's `latex_styles/container_title_style/classic.tex_t`

### 8.5 Three-Tier Merge

The merge order is critical:
```python
deep_update(core_defaults, theme_defaults)  # Theme overrides core
deep_update(result, user_config)            # User overrides theme
```

### 8.6 Per-Part Backgrounds

Part backgrounds are keyed by **integer index** (1, 2, 3...), not by name. The theme checks `latex_toplevel_sectioning == 'part'` before processing.

### 8.7 Sphinx-Needs Conditional

The Sphinx-Needs section in `preamble.tex_t` is only rendered if `'sphinx_needs' in extensions`. This prevents errors when sphinx-needs is not installed.

### 8.8 Inheritance System

When `docdash_inherit_all=True` (default):
- `part` → `chapter` → `section` → `subsection` → `subsubsection`
- For each property (font, color, size), the first non-None value flows downward
- `inherit_size=False` by default (KOMA handles scaling natively)

### 8.9 Part Number Splitting

The part number ("Part I") can be split:
- `part_number_part_*` — Styles for the word "Part"
- `part_number_number_*` — Styles for the number "I"
- Falls back to `part_number_*` if not set

---

## 9. Core vs Theme Comparison

| Aspect | Core (`docdash-pdf-theme-core-dev`) | Theme (`docdash_pdf_theme`) |
|--------|-------------------------------------|------------------------------|
| Role | Shared library / base engine | Default theme that showcases core |
| Config | Three-tier merge from CORE_CONFIG_MANIFEST | Flat config values from setup() |
| Fallbacks | Absolute fallback strings in `core_fallbacks.py` | Theme's `default.tex_t` files |
| Style paths | `docdash_*_style_path` globals | `docdash_*_style_path` config values |
| Dependencies | Depends on Sphinx + Jinja2 | Depends on Sphinx + Jinja2 + core (conceptually) |
| Version | 0.0.129 | 0.1.166 |

**Note:** The theme does NOT import from the core. It ports the utilities directly. This is by design — the theme should be installable as a standalone package.

---

## 10. Quick Reference: All Config Keys

### Flat Config Values (alphabetical)
```
docdash_admonition_caution_title_icon_color
docdash_admonition_caution_title_icon_box_background_color
docdash_admonition_caution_title_background_color
docdash_admonition_warning_title_icon
docdash_admonition_warning_title_icon_color
docdash_admonition_warning_title_background_color
docdash_admonition_warning_title_icon_padding
docdash_admonition_warning_title_decoration_spacing
docdash_admonition_warning_title_icon_box_background_color
docdash_chapter_align
docdash_chapter_line_color
docdash_chapter_line_height
docdash_chapter_number_color
docdash_chapter_number_font
docdash_chapter_number_line
docdash_chapter_number_size
docdash_chapter_number_margin
docdash_chapter_color
docdash_chapter_font
docdash_chapter_size
docdash_containers
docdash_date_color
docdash_date_font
docdash_date_size
docdash_draft
docdash_epigraphs
docdash_footskip
docdash_footer_logo
docdash_footer_logo_height
docdash_headheight
docdash_headsep
docdash_headings
docdash_inherit_all
docdash_inherit_color
docdash_inherit_font
docdash_inherit_size
docdash_main_font
docdash_main_font_options
docdash_mono_font
docdash_needs
docdash_needs_content_background_color
docdash_needs_content_font
docdash_needs_content_font_color
docdash_needs_content_font_size
docdash_needs_metadata_background_color
docdash_needs_metadata_font
docdash_needs_metadata_font_color
docdash_needs_metadata_key_color
docdash_needs_metadata_key_font
docdash_needs_metadata_key_font_size
docdash_needs_segmentation_color
docdash_needs_segmentation_style
docdash_needs_title_background_color
docdash_needs_title_color
docdash_needs_title_font
docdash_needs_title_font_size
docdash_needs_title_icon
docdash_needs_title_icon_color
docdash_needs_title_icon_raise
docdash_needs_title_icon_raise_offset
docdash_needs_title_icon_size
docdash_needs_title_vertical_position
docdash_parts
docdash_part_color
docdash_part_font
docdash_part_number_color
docdash_part_number_font
docdash_part_number_part_color
docdash_part_number_part_font
docdash_part_number_size
docdash_part_number_number_color
docdash_part_number_number_font
docdash_rubric_color
docdash_rubric_font
docdash_rubric_size
docdash_show_release
docdash_sans_font
docdash_section_color
docdash_section_font
docdash_section_number_color
docdash_section_number_font
docdash_section_number_line
docdash_section_number_margin
docdash_section_size
docdash_section_margin_space
docdash_subsection_color
docdash_subsection_font
docdash_subsection_number_color
docdash_subsection_number_font
docdash_subsection_number_line
docdash_subsection_number_margin
docdash_subsection_size
docdash_subsection_margin_space
docdash_subsubsection_color
docdash_subsubsection_font
docdash_subsubsection_number_color
docdash_subsubsection_number_font
docdash_subsubsection_number_line
docdash_subsubsection_number_margin
docdash_subsubsection_size
docdash_subsubsection_margin_space
docdash_subtitle
docdash_title_color
docdash_title_font
docdash_title_page_top_line
docdash_title_size
docdash_release_version_color
docdash_release_version_font
docdash_release_version_size
docdash_author_color
docdash_author_font
docdash_author_size
docdash_headings
docdash_containers
docdash_container_title_style_path
docdash_admonition_style_path
docdash_need_style_path
docdash_title_page_template_path
```

---

## 11. Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | ~1150 | Sphinx extension entry point, config processing, AST processors |
| `utils.py` | ~170 | Color conversion utilities |
| `default_config.py` | ~50 | Default dictionaries for needs & admonitions |
| `preamble.tex_t` | ~500 | Main LaTeX preamble Jinja2 template |
| `latex_styles/admonition/default.tex_t` | ~35 | Default admonition tcolorbox |
| `latex_styles/admonition/note.tex_t` | ~35 | Note admonition tcolorbox |
| `latex_styles/container_title_style/classic.tex_t` | ~2 | Classic container title geometry |
| `latex_styles/container_title_style/floating.tex_t` | ~8 | Floating/chevron title geometry |
| `latex_styles/container_title_style/ribbon.tex_t` | ~10 | Ribbon title geometry |
| `latex_styles/need/default.tex_t` | ~15 | Sphinx-Needs tcolorbox |
| `latex_styles/title_page/default.tex_t` | ~35 | Cover page background injection |
| `latex_styles/sphinxlatexstyleheadings.sty` | — | KOMA heading style overrides |
| `latex_styles/sphinxlatexstylepage.sty` | — | Page layout style overrides |

---

## 12. Core Features Showcased by This Theme

This theme demonstrates all the bells and whistles the core provides:

1. ✅ **Structural Layout** — Alternating margin numbers with decorative lines
2. ✅ **Document Inheritance** — Font/color/size inheritance down the hierarchy
3. ✅ **Universal Element Namespacing** — Per-element font, color, size control
4. ✅ **Custom Container Styles** — Three container title styles (classic, floating, ribbon)
5. ✅ **Custom Admonition Styles** — Two admonition styles (default, note)
6. ✅ **Sphinx-Needs Styling** — Full needs box rendering with metadata/content split
7. ✅ **Part Backgrounds** — Per-part color/image overlays
8. ✅ **Draft Watermark** — Rotated watermark with date/version injection
9. ✅ **Epigraph/Dictum** — Dynamic dictum with per-level styling
10. ✅ **Title Page** — Custom cover with background image/color support
11. ✅ **Split Part Numbers** — "Part" and number in different fonts/colors
12. ✅ **WCAG Contrast** — Automatic highest-contrast color calculation
13. ✅ **Hex Brightness** — Programmatic color adjustment in conf.py
14. ✅ **Custom Folder Paths** — Override any style path from conf.py
15. ✅ **Three-Tier Merge** — Core → Theme → User configuration cascade
