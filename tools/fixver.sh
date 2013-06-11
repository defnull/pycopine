#!/bin/sh



DIR=`dirname $0`
DIR=`dirname $DIR`
VERSION=`head -n1 $DIR/VERSION`
TAG='\# Do not edit (see VERSION file)'

sed -i "s/__version__.*/__version__ = '$VERSION' $TAG/" $DIR/pycopine/__init__.py
sed -i "s/version *=.*/version = '$VERSION', $TAG/" $DIR/setup.py
sed -i "s/release *=.*/release = '$VERSION' $TAG/" $DIR/docs/conf.py
