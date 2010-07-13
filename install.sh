#!/bin/bash

# This software and any associated files are copyright 2010 Brian Carver and
# Michael Lissner.
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#  Under Sections 7(a) and 7(b) of version 3 of the GNU Affero General Public
#  License, that license is supplemented by the following terms:
#
#  a) You are required to preserve this legal notice and all author
#  attributions in this program and its accompanying documentation.
#
#  b) You are prohibited from misrepresenting the origin of any material
#  within this covered work and you are required to mark in reasonable
#  ways how any modified versions differ from the original version.

# This script is designed to install the CourtListener project on a Linux 
# machine. It was written for Ubuntu Lucid Linux - v. 10.04, but should work on
# most debian derivatives.
#
# This script should also serve as the documentation for the installation 
# process.

# This script does the following:
# - check for its own dependencies (such as aptitude, hg, svn, etc)
# - get various input from the user.
# - install django from source
# - install CourtListener from source
# - install & configure Sphinx
# - install django-sphinx
# - configure mysql & courtlistener
# - install the django-debug toolbar
# - sync the django configuration with the database
# - exit

# It's a monster...hopefully one that works.


function printHelp {
cat <<EOF
NAME
    install.sh

SYNOPSIS
    install.sh --help | --install

OPTIONS
    This program will install the courtlistener software on your computer. It 
    makes a number of assumptions, but does its best. Patches and contributions
    are welcome.
    
    Standard Options
    --help      Print this help file
    --install   Install all components of the courtlistener software
    
    Untested Options
    --checkdeps
            Verify that the required dependencies are installed.
    --mysql
            Configure the MySQL database
    --sphinx
            install the Sphinx search engine
    --django
            install Django
    --courtListener
            set up the CL repository, and configure it with django
    --debugToolbar
            install the django debug toolbar
    --djangoSphinx
            install the django-sphinx connector
    --finalize
            finalize the installation

EXIT STATUS
    0   The installation was successful.
    >0  An error occured, as follows:
        1   Unknown error
        2   Invalid usage
        3   Missing critical dependency
        4   Errors installing django from source
        5   Error getting user input
        6   Error installing Sphinx
        7   Error configuring MySQL

AUTHOR AND COPYRIGHT
    This script was authored by Michael Lissner and is released under the same 
    permissive license as the remainder of the courtlistener program.

EOF
}


function getUserInput {
cat<<EOF
Welcome to the install script. This script will install the courtlistener system 
on your Debian-based Linux computer. We will begin by gathering several pieces 
of input from you, and then we will install django, courtlistener, sphinx, 
django-sphinx, django-debug toolbar, MySQL, and all their dependencies.

EOF
    read -p "Shall we continue? (y/n): " proceed
    if [ $proceed != 'y' ]
    then
        exit 2
    else
        sleep 0.5
        echo -e "\nGreat. Off we go.\n"
    fi
    
    # this function sets some variables that will be used throughout the program
    read -p "The default location for your django installation is /opt. Is this OK? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        read -p "Where shall we install django (starting at /, no trailing slash)?: " DJANGO_INSTALL_DIR
    else
        DJANGO_INSTALL_DIR='/opt'
    fi
    
    # set up the PYTHON_SITES_PACKAGES_DIR
    PYTHON_SITES_PACKAGES_DIR=`python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()"`
    read -p "The default location for your CourtListener installation is /var/www. Is this OK? (y/n): " proceed
    if [ $proceed == 'n' ]
    then
        read -p "Where shall we install CourtListener (starting at /, no trailing slash)?: " CL_INSTALL_DIR
    else
        CL_INSTALL_DIR='/var/www'
    fi
    
    # set up the private settings file
    echo -e "\nWe are going to set up two settings files. One with private data, and one with 
public data. For the private data, we will need to gather some information. 
This file should NEVER be checked into revision control!
"
    read -p "What name would you like used as the admin name for the site (e.g. Michael Lissner): " CONFIG_NAME
    read -p "What email address should be used for the admin of the site (e.g. mike@courtlistener.com): " CONFIG_EMAIL
    echo -e "\nGreat. These are stored in a tuple in the 20-private.conf file. You can add more
people manually, if you like.
\nMANAGERS is set equal to the admins.
DEBUG is set to True.
CACHE_BACKEND is not set (which is fine for a dev machine).
TEMPLATE_DEBUG is set to DEBUG.
DEVELOPMENT is set to True (which helps with the runserver command, see urls.py for details).
TIME_ZONE is set to America/Los Angeles
"
    
    # set up the MySQL configs
    read -p "We will be setting up a MySQL DB. What would you like its name to be (e.g. courtListener): " MYSQL_DB_NAME
    read -p "And we will be giving it a username. What would you like that to be (e.g. courtListener): " MYSQL_USERNAME
    MYSQL_PWD=`python -c 'from random import choice; print "".join([choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(30)]);'`
    echo -e "\nYou can set up the MySQL password manually, but we recommend a randomly 
generated password, since you should not ever need to type it in.
"
    read -p "Use the following random password: '$MYSQL_PWD'? (y/n): " proceed
    if [ $proceed == 'n' ]
    then
        read -p "Very well. What would you like the password to be: " MYSQL_PWD
    fi
    
    read -p "
Great. This is all the input we need for a while. We will now complete the 
installation process.

Press any key to proceed, or Ctrl+C to abort. " proceed
}


function checkDeps {
    # this function checks for various dependencies that the script assumes are 
    # installed for its own functionality.
    deps=(aptitude mercurial subversion git-core python python-beautifulsoup python-docutils python-mysqldb python-pip python-setuptools poppler-utils mysql-client mysql-server wget tar libmysqlclient-dev gcc g++ make)
    echo -e "\n########################"
    echo "Checking dependencies..."
    echo "########################"
    read -p "Do you need to check and install dependencies? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi
    
    for dep in ${deps[@]}
    do
        echo -n "Checking for $dep..."
        sleep 0.5
        if dpkg -l $dep 2>/dev/null | grep -q ^.i
        then
            echo "found."
        else
            echo "MISSING."
            if [ $dep == "aptitude" ]
            then
                echo "Aborting. Fatal error. Please install aptitude and try again."
                exit 3
            else
                missingDeps=( ${missingDeps[@]-} $dep )
            fi
        fi
    done
    
    if [ $missingDeps ]
    then
        echo -e "\nThe following dependencies are missing: "
        echo "  ${missingDeps[@]-}"
        read -p "Install? (y/n): " proceed
        if [ $proceed == "y" ]
        then
            # after checking everything, install missing things, with user permission.
            aptitude install -P ${missingDeps[@]-}
            if [ $? != "0" ]
            then
                echo "Unable to properly install dependencies. Exiting."
                exit 3
            fi
        else
            echo "Unable to properly install dependencies. Aborting."
            exit 3
        fi
    fi
    echo -e "\nAll dependencies installed successfully."
}


function installDjango {
    # this process simply installs django. Configuration is done later.
    echo -e "\n####################"
    echo "Installing django..."
    echo "####################"
    read -p "Would you like to download and configure django? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi
    
    if [ ! -d $DJANGO_INSTALL_DIR ]
    then
        read -p "Directory '$DJANGO_INSTALL_DIR' doesn't exist. Create it? (y/n): " proceed
        if [ $proceed == "n" ]
        then
            echo "Bad juju. Aborting."
            exit 5
        else
            mkdir -p $DJANGO_INSTALL_DIR
        fi
    fi

    # get django!
    echo "Downloading django with svn..."
    cd $DJANGO_INSTALL_DIR
    svn co http://code.djangoproject.com/svn/django/trunk/ django-trunk
    
    # link django with python
    if [ ! -d $PYTHON_SITES_PACKAGES_DIR ]
    then
        echo "PYTHON_SITES_PACKAGES_DIR does not exist. Aborting."
    else
        echo -n "Linking python with django..."
        sleep 0.5
        ln -s `pwd`/django-trunk/django $PYTHON_SITES_PACKAGES_DIR/django
        echo "Done."
    fi
    echo -e "\nDjango installed successfully."
}


function installCourtListener {
    # this is probably the most tricky part of the operation. We get the courtlistener
    # code, place it in the correct location, and then configure the heck out of
    # it.
    echo -e "\n########################"
    echo "Downloading and configuring CourtListener itself..."
    echo "########################"
    read -p "Would you like to download and configure CourtListener? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi
    
    if [ ! -d $CL_INSTALL_DIR ]
    then
        read -p "Directory '$CL_INSTALL_DIR' doesn't exist. Create it? (y/n): " proceed
        if [ $proceed == "n" ]
        then
            echo "Bad juju. Aborting."
            exit 5
        else
            mkdir -p $CL_INSTALL_DIR
        fi
    fi
    cd $CL_INSTALL_DIR
    echo "Downloading CourtListener with mercurial..."
    hg clone https://mlissner@bitbucket.org/mlissner/legal-current-awareness court-listener

    # begin the harder thing: configuring it correctly...    
    # We need a link between the 20-private.conf adminMedia location and the 
    # location of the django installation. Else, admin templates won't work.
    ln -s $DJANGO_INSTALL_DIR/django-trunk/django/contrib/admin/media court-listener/alert/assets/media/adminMedia
    
    # and we link up the init scripts
    echo "Installing init scripts."
    ln -s $CL_INSTALL_DIR/court-listener/init-scripts/scraper-init-script.sh /etc/init.d/scraper
        
    # this generates a nice random number, as it is done by django-admin.py
    SECRET_KEY=`python -c 'from random import choice; print "".join([choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for i in range(50)]);'`
    # this is the MEDIA_ROOT
    MEDIA_ROOT="$CL_INSTALL_DIR/court-listener/alert/assets/media/"
    TEMPLATE_DIRS="$CL_INSTALL_DIR/court-listener/alert/assets/templates/"
    
    # all settings should be in place. Now we make the file...
    echo -e "\nGenerating the installation config, 20-private.conf..."
cat <<EOF > $CL_INSTALL_DIR/court-listener/alert/settings/20-private.conf
ADMINS = (
    ('$CONFIG_NAME', '$CONFIG_EMAIL'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'mysql', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': '$MYSQL_DB_NAME',                      # Or path to database file if using sqlite3.
        'USER': '$MYSQL_USERNAME',                      # Not used with sqlite3.
        'PASSWORD': '$MYSQL_PWD',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# Make this unique, and don't share it with anybody.
SECRET_KEY = '$SECRET_KEY'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/adminMedia/'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'
MEDIA_ROOT = '$MEDIA_ROOT'

DEBUG = True

TEMPLATE_DIRS = (
    # put strings here, like "home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, evn on Windows.
    # Don't forget to use absolute paths, not relative paths.
    '$TEMPLATE_DIRS',
)


TEMPLATE_DEBUG = DEBUG

DEVELOPMENT = True

#EMAIL_BACKEND is set to default, so nothing listed here.

# this setting helps with settings elsewhere...include a trailing slash!
INSTALL_ROOT = '$CL_INSTALL_DIR/court-listener/'

EOF

    echo -e 'Done\n\nCourtListener installed and configured successfully.'
}


function configureMySQL {
    echo -e "\n####################"
    echo "Configuring MySQL..."
    echo "####################"
    read -p "Would you like to configure MySQL? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi

    # create and configure the db.
    # first, we make a SQL script, then we execute it, then we delete it.
    # this will also set up a table for Sphinx's main+delta scheme. Kludgy.
cat <<EOF > install.sql
CREATE DATABASE $MYSQL_DB_NAME;
GRANT ALL ON $MYSQL_DB_NAME.* to $MYSQL_USERNAME WITH GRANT OPTION;
SET PASSWORD FOR $MYSQL_USERNAME = password('$MYSQL_PWD');
FlUSH PRIVILEGES;
USE $MYSQL_DB_NAME;
CREATE TABLE sph_counter
(
    counter_id INTEGER PRIMARY KEY NOT NULL,
    max_doc_id INTEGER NOT NULL
);
EOF
    echo "We are about to create the database $MYSQL_DB_NAME, with username
$MYSQL_USERNAME and password $MYSQL_PWD."
    read -p "Press any key to continue, or Ctrl+C to abort. " proceed
    sleep 1
    echo "Please enter your root MySQL password."
    mysql -u'root' -p < install.sql
    if [ $? == "0" ]
    then
        rm install.sql
        echo -e '\nMySQL configured successfully.'
    else
        echo -e '\nError configuring MySQL. Aborting.'
        exit 7
    fi    
}


function installSphinx {
    echo -e "\n####################"
    echo "Installing Sphinx..."
    echo "####################"
    read -p "Would you like to install Sphinx? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi
    
    cd $CL_INSTALL_DIR/court-listener/Sphinx
    wget http://www.sphinxsearch.com/downloads/sphinx-0.9.9.tar.gz
    tar xzvf sphinx-0.9.9.tar.gz; rm sphinx-0.9.9.tar.gz
    cd sphinx-0.9.9
    ./configure --with-prefix=/usr/local/sphinx
    make
    if [ $? == "0" ]
    then
        make install
        if [ $? == '0' ]
        then
            cd ../
            rm -r sphinx-0.9.9
        fi
    else
        echo "Error building Sphinx. Aborting."
        exit 6
    fi
    
    # next we configure the thing...this is going to be ugly.
    # note: EOF without quotes interprets variables and backslashes. To preserve
    # things with either \ or $foo, use 'EOF'
cat <<EOF > $CL_INSTALL_DIR/court-listener/Sphinx/conf/sphinx.conf
source Document
{
    type                = mysql
    sql_host            = localhost
    sql_user            = $MYSQL_USERNAME
    sql_pass            = $MYSQL_PWD
    sql_db              = $MYSQL_DB_NAME
    sql_port            =   
EOF

# In this section, we need the $variables to not get interpreted by bash...
cat <<'EOF' >> $CL_INSTALL_DIR/court-listener/Sphinx/conf/sphinx.conf
    sql_query_pre       = SET NAMES utf8
    sql_query_pre       = REPLACE INTO sph_counter SELECT 1, MAX(documentUUID) FROM Document
    sql_query_post      =
    sql_query_range     = SELECT min(documentUUID), max(documentUUID) from Document
    sql_range_step      = 5000
    sql_query           = \
        SELECT Document.documentUUID, Citation.caseNameShort as caseName, Citation.caseNameFull, Citation.caseNumber as caseNumber, Citation.officialCitationWest, Citation.officialCitationLexis, Document.documentSHA1, UNIX_TIMESTAMP(Document.dateFiled) as dateFiled, UNIX_TIMESTAMP(Document.time_retrieved) as time_retrieved, Document.court_id as court, Document.documentPlainText as docText, Document.documentHTML as docHTML, Document.documentType as docStatus\
        FROM Document, Citation\
        WHERE Document.citation_id = Citation.citationUUID\
	AND Document.documentUUID >= $start\
	AND Document.documentUUID <= $end\
	AND Document.documentUUID <= (SELECT max_doc_id FROM sph_counter WHERE counter_id=1);
        
    sql_query_info      = SELECT * FROM `Document` WHERE `documentUUID` = $id

    # ForeignKey's
    sql_attr_uint       = Document.citation_id
    sql_attr_uint       = Document.excerptSummary_id

    # DateField's and DateTimeField's
    sql_attr_timestamp   = dateFiled
    sql_attr_timestamp   = time_retrieved
}

source delta : Document
{
    sql_query_pre = SET NAMES utf8
    sql_query           = \
        SELECT Document.documentUUID, Citation.caseNameShort as caseName, Citation.caseNameFull, Citation.caseNumber as caseNumber, Citation.officialCitationWest, Citation.officia
lCitationLexis, Document.documentSHA1, UNIX_TIMESTAMP(Document.dateFiled) as dateFiled, UNIX_TIMESTAMP(Document.time_retrieved) as time_retrieved, Document.court_id as court, Docu
ment.documentPlainText as docText, Document.documentHTML as docHTML, Document.documentType as docStatus\
        FROM Document, Citation\
        WHERE Document.citation_id = Citation.citationUUID\
	AND Document.documentUUID >= $start\
	AND Document.documentUUID <= $end\
	AND Document.documentUUID > (SELECT max_doc_id FROM sph_counter WHERE counter_id=1);
}
EOF

# in this section, we need the $variables to be interpreted...
cat <<EOF >> $CL_INSTALL_DIR/court-listener/Sphinx/conf/sphinx.conf
index Document
{
    source = Document
    path = $CL_INSTALL_DIR/court-listener/Sphinx/data/Document
    wordforms = $CL_INSTALL_DIR/court-listener/Sphinx/conf/wordforms.txt
    stopwords = $CL_INSTALL_DIR/court-listener/Sphinx/conf/stopwords.txt
    exceptions = $CL_INSTALL_DIR/court-listener/Sphinx/conf/exceptions.txt
    docinfo = extern
        
    # sets the minimum word length to index
    min_word_len = 2
    charset_type = utf-8
    
    # DISABLED DUE TO LACK OF HD SPACE
    # these set up star searching (at a performance hit), but *test, *test* and test* all will work.
    # min_infix_len= 3
    # infix_fields = caseName, docText, docHTML, Citation.caseNameFull, caseNumber
    min_prefix_len = 3
    prefix_fields = caseName, docText, docHTML, Citation.caseNameFull, caseNumber
    enable_star = 1
    
    # enables exact word form searching (=cat)
    index_exact_words = 1
    
    # enables stemming of english words longer than 3 characters
    morphology      = stem_en
    min_stemming_len = 4
    
    # the default character set, with the addition of the hyphen and the removal of the Cryllic set.
    charset_table = 0..9, A..Z->a..z, _, -, U+00A7, a..z
    
    # Enable HTML stripping
    html_strip = 1
}

index delta : Document
{
    source = delta
    path = $CL_INSTALL_DIR/court-listener/Sphinx/data/Delta
}


indexer
{
	# memory limit, in bytes, kiloytes (16384K) or megabytes (256M)
	# optional, default is 32M, max is 2047M, recommended is 256M to 1024M
	mem_limit = 100M

	# maximum IO calls per second (for I/O throttling)
	# optional, default is 0 (unlimited)
	max_iops = 0
}

searchd
{
	# IP address to bind on
	# optional, default is 0.0.0.0 (ie. listen on all interfaces)
	#
	# address = 127.0.0.1
	# address = 192.168.0.1


	# searchd TCP port number
	# mandatory, default is 3312
	port = 3312

	# log file, searchd run info is logged here
	# optional, default is 'searchd.log'
	log = $CL_INSTALL_DIR/court-listener/Sphinx/log/searchd.log

	# query log file, all search queries are logged here
	# optional, default is empty (do not log queries)
	query_log = $CL_INSTALL_DIR/court-listener/Sphinx/log/query.log

	# client read timeout, seconds
	# optional, default is 5
	read_timeout = 5

	# maximum amount of children to fork (concurrent searches to run)
	# optional, default is 0 (unlimited)
	max_children = 30

	# PID file, searchd process ID file name
	# mandatory
	pid_file = $CL_INSTALL_DIR/court-listener/Sphinx/log/searchd.pid

	# max amount of matches the daemon ever keeps in RAM, per-index
	# WARNING, THERE'S ALSO PER-QUERY LIMIT, SEE SetLimits() API CALL
	# default is 1000 (just like Google)
	max_matches = 1000

	# seamless rotate, prevents rotate stalls if precaching huge datasets
	# optional, default is 1
	seamless_rotate	= 1

	# whether to forcibly preopen all indexes on startup
	# optional, default is 0 (do not preopen)
	preopen_indexes	= 0

	# whether to unlink .old index copies on succesful rotation.
	# optional, default is 1 (do unlink)
	unlink_old = 1
}
EOF

    # and hopefully that worked...
    echo -e "\nSphinx installed successfully."
}


function installDjangoSphinx {
    echo -e "\n###########################"
    echo "Installing django-sphinx..."
    echo "###########################"
    read -p "Would you like to install django-sphinx? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi
    
    # we install django-sphinx, and patch it per bug #X
    cd $DJANGO_INSTALL_DIR
    git clone git://github.com/dcramer/django-sphinx.git django-sphinx
    cd django-sphinx
    
    echo -e "\nPatching django-sphinx, since bug fixes aren't handled by its author..."
    
    git apply << 'EOF'
From a3c8c847d1ba6742f0a8e2ae9c69de3d30db42c1 Mon Sep 17 00:00:00 2001
From: root <mike@courtlistener.com>
Date: Mon, 12 Jul 2010 15:20:01 -0700
Subject: [PATCH] Fix for stupid bugs.

---
 djangosphinx/utils/config.py |    6 +++---
 setup.py                     |    1 -
 2 files changed, 3 insertions(+), 4 deletions(-)

diff --git a/djangosphinx/utils/config.py b/djangosphinx/utils/config.py
index 24a1907..18abb10 100644
--- a/djangosphinx/utils/config.py
+++ b/djangosphinx/utils/config.py
@@ -11,8 +11,8 @@ import djangosphinx.apis.current as sphinxapi
 __all__ = ('generate_config_for_model', 'generate_config_for_models')
 
 def _get_database_engine():
-    if settings.DATABASE_ENGINE == 'mysql':
-        return settings.DATABASE_ENGINE
+    if settings.DATABASES['default']['ENGINE'] == 'mysql':
+        return settings.DATABASES['default']['ENGINE']
     elif settings.DATABASE_ENGINE.startswith('postgresql'):
         return 'pgsql'
     raise ValueError, "Only MySQL and PostgreSQL engines are supported by Sphinx."
@@ -188,4 +188,4 @@ def generate_source_for_models(model_classes, index=None, sphinx_params={}):
 
     c = Context(params)
     
-    return t.render(c)
\ No newline at end of file
+    return t.render(c)
diff --git a/setup.py b/setup.py
index 43b8582..c04bf9e 100755
--- a/setup.py
+++ b/setup.py
@@ -10,7 +10,6 @@ setup(
     author='David Cramer',
     author_email='dcramer@gmail.com',
     url='http://github.com/dcramer/django-sphinx',
-    install_requires=['django'],
     description = 'An integration layer bringing Django and Sphinx Search together.',
     packages=find_packages(),
     include_package_data=True,
-- 
1.7.0.4

EOF
    
    python setup.py install
    
    echo -e '\ndjango-sphinx installed successfully.'
}

function installDebugToolbar {
    echo -e '\n##################################'
    echo 'Installing django debug toolbar...'
    echo '##################################
' 
    read -p "Is the django debug toolbar installed on this computer? (y/n): " installed
    if [ $installed == "n" ]
    then
        # we install it
        pip install django-debug-toolbar
        echo -e '\nDjango debug toolbar installed successfully.'
    else
        echo -e '\nGreat. Moving on.'
        return 0
    fi
}


function finalize {
    echo -e '\n##############################'
    echo 'Finalizing the installation...'
    echo '##############################'
    read -p "Would you like to finalize the installation? (y/n): " proceed
    if [ $proceed == "n" ]
    then
        echo -e '\nGreat. Moving on.'
        return 0
    fi
    
    echo -e '\nSyncing the django data model...'
    cd $CL_INSTALL_DIR/court-listener/alert
    python manage.py syncdb
    
    echo -e '\nInstallation finalized successfully.'
}

function main {
    # run the program!
    getUserInput
    checkDeps
    installDjango
    installCourtListener
    configureMySQL
    installSphinx
    installDjangoSphinx
    installDebugToolbar
    finalize

    echo -e "\n\n#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#"
    echo '  CourtListener was completely installed correctly!'
    echo "#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#=#"
    echo "You may test this installation by going to $CL_INSTALL_DIR/court-listener/alert
and running the command:
    $ python manage.py runserver
If that works, you should be able to see the CourtListener website in your browser
at http://localhost:8000.

If you would like Sphinx to start at bootup, add this line to the root's cron file:
@reboot /usr/local/bin/searchd -c $CL_INSTALL_DIR/court-listener/Sphinx/conf/sphinx.conf

That will enable you to search, but your content will also need to be indexed regularly.
Cron jobs such as the following might work well:
20	*	*	*	1-5	/usr/local/bin/indexer -c $CL_INSTALL_DIR/court-listener/Sphinx/conf/sphinx.conf delta --rotate > /dev/null
45	1	1	*/2	*	/usr/local/bin/indexer -c $CL_INSTALL_DIR/court-listener/Sphinx/conf/sphinx.conf Document --rotate

The first updates the delta index once every 20 minutes. The second updates the main
index every other week.
"
    read -p "Press any key to exit the install script, and begin hacking. "
    exit 0
}


#initiation sequence
if [ $# -eq 0 -o $# -gt 1 ]
then
    # We need to give them help using the program. 
    echo "install.sh:  Invalid number of arguments."
    echo "Usage: install.sh --help | --install"
    exit 2
elif [[ $EUID -ne 0 ]]; 
then
    echo "install.sh: This script must be run as root" 1>&2
    exit 2
else
    case $1 in
        --help) printHelp;;
        --install) main;;
        --checkdeps) checkDeps;;
        --mysql) getUserInput; configureMySQL;;
        --sphinx) getUserInput; installSphinx;;
        --django) getUserInput; installDjango;;
        --courtListener) getUserInput; installCourtListener;;
        --debugToolbar) installDebugToolbar;;
        --djangoSphinx) getUserInput; installDjangoSphinx;;
        --finalize) getUserInput; finalize;;
        *) echo "install.sh: Invalid argument. Try the --help argument."
           exit 2;
    esac
fi
