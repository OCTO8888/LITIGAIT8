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

# imports of local settings and views
from alert import settings
from alert.alerts.models import PACER_CODES
from alert.alerts.views import delete_favorite
from alert.alerts.views import edit_favorite
from alert.alerts.views import redirect_short_url
from alert.alerts.views import save_or_update_favorite
from alert.alerts.views import viewCase
from alert.alerts.views import viewDocumentListByCourt
from alert.contact.views import contact, thanks
from alert.data_dumper.views import dump_index, serve_or_gen_dump
from alert.feeds.views import allCourtsFeed, courtFeed, searchFeed
from alert.pinger.views import validateForBing, validateForGoogle, validateForYahoo
from alert.robots.views import robots
from alert.search.views import deleteAlert
from alert.search.views import deleteAlertConfirm
from alert.search.views import editAlert
from alert.search.views import home
from alert.search.views import showResults
from alert.search.views import toolsPage
from alert.userHandling.views import confirmEmail
from alert.userHandling.views import deleteProfile
from alert.userHandling.views import deleteProfileDone
from alert.userHandling.views import emailConfirmSuccess
from alert.userHandling.views import password_change
from alert.userHandling.views import redirect_to_settings
from alert.userHandling.views import register
from alert.userHandling.views import registerSuccess
from alert.userHandling.views import requestEmailConfirmation
from alert.userHandling.views import view_favorites
from alert.userHandling.views import viewAlerts
from alert.userHandling.views import viewSettings

# this imports a variable that can be handed to the sitemap index generator function.
from alert.alerts.sitemap import all_sitemaps as sitemaps
from django.conf.urls.defaults import *

# for the flatfiles in the sitemap
from django.contrib.auth.views import login as signIn
from django.contrib.auth.views import logout as signOut
from django.contrib.auth.views import password_reset
from django.contrib.auth.views import password_reset_done
from django.contrib.auth.views import password_reset_confirm

# enables the admin:
from django.contrib import admin
admin.autodiscover()

# creates a list of the first element of the choices variable for the courts field
pacer_codes = []
for code in PACER_CODES:
    pacer_codes.append(code[0])

urlpatterns = patterns('',
    # Admin docs and site
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),

    # Court listing pages
    (r'^opinions/(' + "|".join(pacer_codes) + '|all)/$', viewDocumentListByCourt),

    # Display a case, a named URL because the get_absolute_url uses it.
    url(r'^(' + "|".join(pacer_codes) + ')/(.*)/(.*)/$', viewCase, name = "viewCase"),
    # Redirect users
    (r'^x/(.*)/$', redirect_short_url),

    # Contact us pages
    (r'^contact/$', contact),
    (r'^contact/thanks/$', thanks),

    # Various sign in/out etc. functions as provided by django
    url(r'^sign-in/$', signIn, name = "sign-in"),
    (r'^sign-out/$', signOut),

    # Homepage and favicon
    (r'^$', home),
    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/media/images/ico/favicon.ico'}),

    # Settings pages
    (r'^profile/$', redirect_to_settings),
    url(r'^profile/settings/$', viewSettings, name = 'viewSettings'),
    (r'^profile/favorites/$', view_favorites),
    (r'^profile/alerts/$', viewAlerts),
    (r'^profile/password/change/$', password_change),
    (r'^profile/delete/$', deleteProfile),
    (r'^profile/delete/done/$', deleteProfileDone),
    url(r'^register/$', register, name = "register"),
    (r'^register/success/$', registerSuccess),
    # Favorites pages
    (r'^favorite/create-or-update/$', save_or_update_favorite),
    (r'^favorite/delete/$', delete_favorite),
    (r'^favorite/edit/(\d{1,6})/$', edit_favorite),

    # Registration pages
    (r'^email/confirm/([0-9a-f]{40})/$', confirmEmail),
    (r'^email-confirmation/request/$', requestEmailConfirmation),
    (r'^email-confirmation/success/$', emailConfirmSuccess),

    #Reset password pages
    (r'^reset-password/$', password_reset),
    (r'^reset-password/instructions-sent/$', password_reset_done),
    (r'^confirm-password/(?P<uidb36>.*)/(?P<token>.*)/$', password_reset_confirm, {'post_reset_redirect': '/reset-password/complete/'}),
    (r'^reset-password/complete/$', signIn, {'template_name': 'registration/password_reset_complete.html'}),

    # Alert/search pages
    # These URLs support either GET requests or things like /alert/preview/searchterm.
    #url(r'^(alert/preview)/$', showResults, name="alertResults"),
    url(r'^search/results/$', showResults, name = "searchResults"),
    (r'^search/$', showResults), #for the URL hackers in the crowd
    (r'^alert/edit/(\d{1,6})/$', editAlert),
    (r'^alert/delete/(\d{1,6})/$', deleteAlert),
    (r'^alert/delete/confirm/(\d{1,6})/$', deleteAlertConfirm),
    (r'^tools/$', toolsPage),

    # Dump index and generation pages
    (r'^dump-info/$', dump_index),
    (r'^dump-api/(?P<court>' + "|".join(pacer_codes) + '|all)\.xml.gz$', serve_or_gen_dump),
    (r'^dump-api/(?P<year>\d{4})/(?P<court>' + "|".join(pacer_codes) + '|all)\.xml.gz$', serve_or_gen_dump),
    (r'^dump-api/(?P<year>\d{4})/(?P<month>\d{2})/(?P<court>' + "|".join(pacer_codes) + '|all)\.xml.gz$', serve_or_gen_dump),
    (r'^dump-api/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<court>' + "|".join(pacer_codes) + '|all)\.xml.gz$', serve_or_gen_dump),

    # Feeds
    (r'^feed/(search)/$', searchFeed()), #lacks URL capturing b/c it will use GET queries.
    (r'^feed/court/all/$', allCourtsFeed()),
    (r'^feed/court/(?P<court>' + '|'.join(pacer_codes) + ')/$', courtFeed()),

    # SEO-related stuff
    (r'^y_key_6de7ece99e1672f2.html$', validateForYahoo),
    (r'^LiveSearchSiteAuth.xml$', validateForBing),
    (r'^googleef3d845637ccb353.html$', validateForGoogle),
    # Sitemap index generator
    (r'^sitemap\.xml$', 'alert.alerts.sitemap.indexCopy',
        {'sitemaps': sitemaps}),
    # this uses a custom sitemap generator that has a file-based cache.
    (r'^sitemap-(?P<section>.+)\.xml$', 'alert.alerts.sitemap.cachedSitemap', {'sitemaps': sitemaps}),
    (r'^robots.txt$', robots)
)

# redirects
urlpatterns += patterns('django.views.generic.simple',
    ('^privacy/$', 'redirect_to', {'url': '/terms/#privacy'}),
    ('^removal/$', 'redirect_to', {'url': '/terms/#removal'}),
    ('^browse/$', 'redirect_to', {'url': '/opinions/all/'}),
    ('^opinions/$', 'redirect_to', {'url': '/opinions/all/'}),
    ('^report/$', 'redirect_to', {'url': 'http://www.ischool.berkeley.edu/files/student_projects/Final_Report_Michael_Lissner_2010-05-07_2.pdf'}),
)


# if it's not the production site, serve the static files this way.
if settings.DEVELOPMENT:
    urlpatterns += patterns('',
    (r'^media/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': settings.INSTALL_ROOT + 'alert/assets/media',
        'show_indexes': True}),
    (r'^500/$', 'django.views.generic.simple.direct_to_template',
        {'template': '500.html'}),
    (r'^404/$', 'django.views.generic.simple.direct_to_template',
        {'template': '404.html'}),
)
