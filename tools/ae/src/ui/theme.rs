//! Colors and glyphs. Truecolor terminals get a Catppuccin-style palette;
//! others get the closest named colors; NO_COLOR gets none.

use ratatui::style::{Color, Modifier, Style};

#[derive(Clone, Copy)]
pub struct Theme {
    pub color: bool,
    truecolor: bool,
}

impl Theme {
    pub fn detect() -> Theme {
        let color = std::env::var_os("NO_COLOR").is_none();
        let truecolor = std::env::var("COLORTERM").is_ok_and(|v| v == "truecolor" || v == "24bit");
        Theme { color, truecolor }
    }

    #[cfg(test)]
    pub fn plain() -> Theme {
        Theme { color: false, truecolor: false }
    }

    fn pick(&self, rgb: (u8, u8, u8), named: Color) -> Style {
        if !self.color {
            return Style::default();
        }
        Style::default().fg(if self.truecolor { Color::Rgb(rgb.0, rgb.1, rgb.2) } else { named })
    }

    pub fn accent(&self) -> Style {
        self.pick((203, 166, 247), Color::Magenta)
    }
    pub fn green(&self) -> Style {
        self.pick((166, 227, 161), Color::Green)
    }
    pub fn red(&self) -> Style {
        self.pick((243, 139, 168), Color::Red)
    }
    pub fn yellow(&self) -> Style {
        self.pick((249, 226, 175), Color::Yellow)
    }
    pub fn peach(&self) -> Style {
        self.pick((250, 179, 135), Color::LightRed)
    }
    pub fn blue(&self) -> Style {
        self.pick((137, 180, 250), Color::Blue)
    }
    pub fn teal(&self) -> Style {
        self.pick((148, 226, 213), Color::Cyan)
    }
    pub fn text(&self) -> Style {
        self.pick((205, 214, 244), Color::Reset)
    }
    pub fn muted(&self) -> Style {
        if self.color { self.pick((127, 132, 156), Color::DarkGray) } else { Style::default().add_modifier(Modifier::DIM) }
    }
    pub fn border(&self) -> Style {
        if self.color { self.pick((88, 91, 112), Color::DarkGray) } else { Style::default() }
    }
    pub fn focus_border(&self) -> Style {
        self.accent()
    }
    pub fn bold(&self) -> Style {
        Style::default().add_modifier(Modifier::BOLD)
    }
    /// The cursor cell or row.
    pub fn cursor(&self) -> Style {
        if !self.color {
            return Style::default().add_modifier(Modifier::REVERSED);
        }
        let bg = if self.truecolor { Color::Rgb(69, 71, 90) } else { Color::DarkGray };
        Style::default().bg(bg).add_modifier(Modifier::BOLD)
    }
    pub fn row_highlight(&self) -> Style {
        if !self.color {
            return Style::default().add_modifier(Modifier::BOLD);
        }
        let bg = if self.truecolor { Color::Rgb(49, 50, 68) } else { Color::Reset };
        Style::default().bg(bg)
    }
}

pub const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
