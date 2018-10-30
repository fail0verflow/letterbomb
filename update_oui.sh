#!/bin/sh
wget -O - http://standards.ieee.org/develop/regauth/oui/oui.txt | grep -i nintendo | grep base\ 16  | awk '{print $1}' | sort > oui_list.txt.new || exit 1
diff -urN oui_list.txt oui_list.txt.new
mv oui_list.txt oui_list.txt.old
mv oui_list.txt.new oui_list.txt
