#! /usr/bin/env bash
[ -z $(which phantomjs) ] && echo "Need phantomjs to create output report files!" && exit 
python Main.py "$(pwd)/inputfolder" "$(pwd)/outputfolder"