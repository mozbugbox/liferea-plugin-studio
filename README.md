# liferea-plugin-studio
Collection of liferea plugins

# Plugins
* blocklink: *[Don't work anymore]* Block unwanted URLs for the Web view.
  
   Depends on `adblockparser.py`. This could be **quite slow**
   with large block list. Don't use this plugin on slow machine.

* Shades: Substitute bright/white background colors with a darker background
  color in Web view.
* WebKitSetting: Access settings of `WebKit` environment.
* Accels: Edit accelarators/shortcuts for Liferea actions.
* Extra Actions: Add some extra user actions which can be bind to
  shorcut keys using `Accels` plugin.
* Search Better: Tweak the search on feedlist and itemlist treeview.
* Search PinYin: Use PinYin to search in feedlist and itemlist treeview.

# Dependency
* Liferea: version >= 1.12.3
* Libpeas with loader for python3 compiled into Liferea
* ~~[adblockparser.py](https://github.com/scrapinghub/adblockparser): required
  by the `blocklink` plugin.~~

# Installation
Each plugin is kept in its own directory.

To install a plugin, copy the desired plugin directory into
`~/.local/share/liferea/plugins/`. Then turn on the plugin in Liferea throught
the menu `Tools->Preferences->Plugins`.

E.g., to install the `webkitsetting` plugin:

```sh
wget "https://github.com/mozbugbox/liferea-plugin-studio/archive/master.zip"
unzip liferea-plugin-studio-master.zip
cd liferea-plugin-studio-master
cp -R webkitsetting ~/.local/share/liferea/plugins/
```

Or use `git`

```sh
mkdir src
cd src
git clone https://github.com/mozbugbox/liferea-plugin-studio/
cd liferea-plugin-studio
cp -R webkitsetting ~/.local/share/liferea/plugins/
```

