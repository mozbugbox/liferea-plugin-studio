# liferea-plugin-studio
Collection of liferea plugins

# Plugins
* blocklink: Block unwanted URLs for the Web view
* Shades: Substitude bright/white background colors with a darker background color in Web view
* shortcuts: A few extra shortcut keys for skim the feeds
* webkitsetting: Access settings of `WebKit` and `Soup` environment 

# Dependency
* Liferea: version >= 1.11.3 (current git master as of 2015-04-08)
* Libpeas with loader for python 2.7 compiled into Liferea
* [adblockparser.py](https://github.com/scrapinghub/adblockparser): required by the `blocklink` plugin.

# Installation
Each plugin is kept in its own directory.

To install a plugin, copy the desired plugin directory into `~/.local/share/liferea/plugins/`. Then turn on the plugin in Liferea throught the menu `Tools->Preferences->Plugins`.

E.g., to install the `webkitsetting` plugin:
```
$ mkdir src
$ cd src
$ git clone https://github.com/mozbugbox/liferea-plugin-studio/
$ cd liferea-plugin-studio
$ cp -R webkitsetting ~/.local/share/liferea/plugins/
```

