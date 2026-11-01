Sean's Outfit Swap 1.0.0
=======================

Every disguise in The Saboteur wears the soldier's real tunic, collar and tie instead of Sean's own
open-shirted clothes.

INSTALL
  1. Close the game.
  2. Double-click "Install Sean's Outfit Swap.bat".
     If the game is not in C:\Saboteur\The Saboteur, pass the folder:
        "Install Sean's Outfit Swap.bat" "D:\Games\The Saboteur"
  3. Start the game and put on a disguise.

  Needs Python 3.8 or newer (py -3 or python on PATH).  Nothing is installed system-wide.

STATUS / UNINSTALL
  "Status.bat"                  shows whether the mod is installed.
  "Uninstall Sean's Outfit Swap.bat"   removes it and restores the stock pack.

WHAT IT CHANGES
  France\loosefiles_BinPC.pack   GameTemplates.wsd and global.map only (patched in place)
  Global\patchdynamic0.megapack  added, 45.6 MB

  Global\Dynamic0.megapack and Saboteur.exe are untouched.  Other mods that edit the same pack survive.

SAVES
  A save made while disguised with this mod stores the uniform's body-part ids.  Keep the mod installed if
  you want to load those saves; uninstalling first can leave such a save without its tunic.

BACKUPS
  Every pack the installer replaces is copied to installer\backups\, named by its sha256.  If an install or
  uninstall fails it rolls the game folder back by itself and says so.

  To restore a backup by hand: find your pack's original sha256 (Status.bat prints the current one), copy
  installer\backups\loosefiles_BinPC.pack.<sha> over France\loosefiles_BinPC.pack, and delete
  Global\patchdynamic0.megapack.

STATUS OF THIS BUILD
  The install is byte-exact and the data checks pass, but the mod has not been run in game.  Version 1.0.0
  is a test build: expect to report back whether the tunic fits Sean's shoulders and whether Continue works
  on a save made in disguise.

  Full notes: README.md, docs\MECHANISM.md, docs\VERIFICATION.md
