# default_config.py

"""
DocDash Theme Defaults

This module contains the baseline dictionary structures and default values 
for the DocDash layout engine. Theme authors can reference these structures 
when overriding settings in their project's conf.py.
"""

# --- DEFAULT SPHINX-NEEDS STYLING ---
# Applied when a specific need type (like 'dr' or 'req') lacks explicit configuration.
DEFAULT_NEEDS_CONFIG = {
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

# --- DEFAULT ADMONITION STYLING ---
# The master fallback for standard Sphinx admonitions.
DEFAULT_ADMONITION_CONFIG = {
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