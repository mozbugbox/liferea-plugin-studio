// vim:fileencoding=utf-8:sw=2:et

/**
 * JS that add shades to light document background
 *
 * Copyright (C) 2015 Mozbugbox <mozbugbox@yahoo.com.au>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 3 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public License
 * along with this library; see the file COPYING.LIB.  If not, write to
 * the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 *
 **/
(function(LifereaShades, undefined) {
  LifereaShades.rgb_cache = {};
  LifereaShades.hsl_cache = {};
  LifereaShades.color_cache = {};
  LifereaShades.SHADE_TAGS = [
      'iframe',
      'address',
      'article',
      'aside',
      'blockquote',
      'body',
      'cite',
      'code',
      'dd',
      'div',
      'dl',
      'details',
      'fieldset',
      'figcaption',
      'figure',
      'font',
      'footer',
      'form',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'header',
      'hgroup',
      'hr',
      'li',
      'main',
      'math',
      'nav',
      'noscript',
      'ol',
      'output',
      'p',
      'pre',
      'q',
      'section',
      'span',
      'table',
      'tbody',
      'td',
      'textarea',
      'tfoot',
      'ul'
  ];

  // http://stackoverflow.com/a/9493060
  // Convert HSL color system to RGB
  LifereaShades.hslToRgb = function(h, s, l) {
    var ret;
    var hashkey = [h, s, l].join(":");
    if (LifereaShades.hsl_cache.hasOwnProperty(hashkey)) {
      ret = LifereaShades.hsl_cache[hashkey];
      return ret.slice();
    }

    var r, g, b;
    if (s == 0) {
      r = g = b = l; // achromatic
    } else {
      var hue2rgb = function hue2rgb(p, q, t) {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1 / 6) return p + (q - p) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
        return p;
      };
      var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      var p = 2 * l - q;
      r = hue2rgb(p, q, h + 1 / 3);
      g = hue2rgb(p, q, h);
      b = hue2rgb(p, q, h - 1 / 3);
    }
    ret = [r, g, b].map(function(x) {
      return Math.round(x * 255);
    });
    LifereaShades.hsl_cache[hashkey] = ret;
    return ret.slice();
  };

  // Convert RGB color system to HSL
  LifereaShades.rgbToHsl = function(r, g, b) {
    var ret;
    var hashkey = [r, g, b].join(":");
    if (LifereaShades.rgb_cache.hasOwnProperty(hashkey)) {
      ret = LifereaShades.rgb_cache[hashkey];
      return ret.slice();
    }

    r /= 255, g /= 255, b /= 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    var h, s, l;
    l = (max + min) / 2;

    if (max == min) {
        h = s = 0; // achromatic
    } else {
        var d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = (g - b) / d + (g < b ? 6 : 0); break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }
        h /= 6;
    }

    ret = [h, s, l];

    LifereaShades.rgb_cache[hashkey] = ret;
    return ret.slice();
  };

  // Parse color in the form of rgba(255, 255, 255, 0.5)
  LifereaShades.parse_rgb = function(color_str) {
    var ret;
    if (LifereaShades.color_cache.hasOwnProperty(color_str)) {
      ret = LifereaShades.color_cache[color_str];
      return ret.slice();
    }
    var pindex = color_str.indexOf('(');
    var color_str = color_str.slice(pindex + 1, color_str.length - 1);
    ret = color_str.split(',').map(function(x, a) {
      return parseFloat(x);
    });
    LifereaShades.color_cache[color_str] = ret;
    return ret.slice();
  };

  // Add shade elements of tagname
  LifereaShades.shade_tag = function(win, tagname, threshold, new_lit) {
    var doc = win.document;
    var new_color = null;
    var new_rgb = null;
    var new_bg_lit = null;

    var min_lit_gap = 0.3;
    var min_hue_gap = 30.0 / 360; // hue is [0, 1)

    if (typeof new_lit === 'string') {
      if (new_lit.slice(0, 3) === 'rgb') {
        new_rgb = LifereaShades.parse_rgb(new_lit);
      }
      new_color = new_lit;
    }

    var elms = doc.getElementsByTagName(tagname);
    for (var i = 0; i < elms.length; i++) {
      var elm = elms[i];
      var styleobj = win.getComputedStyle(elm, null);

      var bgcolor = styleobj.getPropertyValue('background-color');
      //console.log(bgcolor);
      if (bgcolor.slice(0, 3) !== 'rgb') {
        if (tagname == "body") {
          elm.style.backgroundColor = "rgb(126, 126, 126)";
        }
        continue;
      }
      var rgb = LifereaShades.parse_rgb(bgcolor);
      var hsl = LifereaShades.rgbToHsl(rgb[0], rgb[1], rgb[2]);
      if (hsl[2] <= threshold) {
        continue;
      }

      if (typeof new_lit === 'number') {
        new_rgb = LifereaShades.hslToRgb(hsl[0], hsl[1], new_lit);
      }

      if (new_rgb !== null) {
        if (rgb.length == 4) {
          new_rgb[3] = rgb[3];
          new_color = 'rgba(' + new_rgb.join(',') + ')';
        } else {
          new_color = 'rgb(' + new_rgb.join(',') + ')';
        }
      }
      //console.log('new color:', new_color, elm.style.backgroundColor);
      // Need to set "important" to override !important css
      elm.style.setProperty("background-color", new_color, "important");

      // try to keep min differential b/w foreground and background color
      // If the foreground light is too close to the new background light
      // Try to regain the original distance between foreground and background
      var fgcolor = styleobj.getPropertyValue('color');
      if (fgcolor.slice(0, 3) !== 'rgb') {
        continue;
      }

      if (new_bg_lit === null) {
        var new_bg = styleobj.getPropertyValue('background-color');
        var nr = LifereaShades.parse_rgb(new_bg);
        var new_bg_hsl = LifereaShades.rgbToHsl(nr[0], nr[1], nr[2]);
        new_bg_lit = new_bg_hsl[2];
      }

      var fg_rgb = LifereaShades.parse_rgb(fgcolor);
      var fg_hsl = LifereaShades.rgbToHsl(fg_rgb[0], fg_rgb[1], fg_rgb[2]);
      //console.log(fgcolor, fg_rgb, fg_hsl, fg_hsl[2], hsl);
      if (Math.abs(fg_hsl[2] - new_bg_lit) < min_lit_gap &&
        Math.abs(fg_hsl[0] - hsl[0]) < min_hue_gap) {
        fg_light = new_bg_lit + fg_hsl[2] - hsl[2];
        if (fg_light < 0) {
          fg_light = 0;
        } else if (fg_light > 1) {
          fg_light = 1;
        }
        var new_fgcolor;
        var new_fg = LifereaShades.hslToRgb(fg_hsl[0], fg_hsl[1], fg_light);
        //console.log(new_fg)

        if (fg_rgb.length == 4) {
          new_fg[3] = fg_rgb[3];
          new_fgcolor = 'rgba(' + new_fg.join(',') + ')';
        } else {
          new_fgcolor = 'rgb(' + new_fg.join(',') + ')';
        }
        elm.style.setProperty("color", new_fgcolor, "important");
      }
    }
  };

  // Add shade to all the window frames
  LifereaShades.shade_window = function(win, threshold, new_lit) {
    var tags = LifereaShades.SHADE_TAGS;
    for (var i = 0; i < tags.length; i++) {
      var tag = tags[i];
      LifereaShades.shade_tag(win, tag, threshold, new_lit);
    }

    var framelist = win.frames;
    for (var j = 0; j < framelist.length; j++) {
      var frame = framelist[j];
      try {
        LifereaShades.shade_window(frame, threshold, new_lit);
      } catch (e) {
        console.log(e);
      }
    }
  };

  LifereaShades.do_shade = function(threshold, new_lit) {
    LifereaShades.shade_window(window, threshold, new_lit);
  };

  // Set background color if it is not set
  LifereaShades.set_background = function(background_color) {
    var bgcolor = window.document.body.style.backgroundColor;
    if (!bgcolor) {
      window.document.body.style.backgroundColor = background_color;
    }
  };

}(window.LifereaShades = window.LifereaShades || {}));

//LifereaShades.shade_window(window, 0.2, "#888888");
