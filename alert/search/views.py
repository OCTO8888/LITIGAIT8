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

from alert.alerts.forms import CreateAlertForm
from alert.lib import sunburnt
from alert.search.forms import SearchForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.paginator import PageNotAnInteger
from django.core.paginator import EmptyPage
from django.conf import settings
from django.shortcuts import render_to_response
from django.shortcuts import HttpResponseRedirect
from django.template import RequestContext
from django.utils.datastructures import MultiValueDictKeyError

conn = sunburnt.SolrInterface(settings.SOLR_URL, mode='r')

def get_date_filed_or_return_zero(doc):
    """Used for sorting dates. Returns the date field or the earliest date
    possible in Python. With this done, items without dates will be listed
    last without throwing errors to the sort function."""
    if (doc.dateFiled != None):
        return doc.dateFiled
    else:
        import datetime
        return datetime.date(1, 1, 1)


def show_results(request):
    solr_log = open('/var/log/solr/solr.log', 'a')
    solr_log.write('\n\n')
    solr_log.close()
    print
    print
    print "Running the show_results view..."
    '''Show the results for a query
    
    Implements a parallel faceted search interface with Solr as the backend.
    '''

    query = request.GET.get('q', '*')


    # this handles the alert creation form.
    if request.method == 'POST':
        # an alert has been created
        alert_form = CreateAlertForm(request.POST)
        if alert_form.is_valid():
            cd = alert_form.cleaned_data

            # save the alert
            a = CreateAlertForm(cd)
            alert = a.save()

            # associate the user with the alert
            up = request.user.get_profile()
            up.alert.add(alert)
            messages.add_message(request, messages.SUCCESS,
                                 'Your alert was created successfully.')

            # and redirect to the alerts page
            return HttpResponseRedirect('/profile/alerts/')
    else:
        # the form is loading for the first time, load it, then load the rest
        # of the page
        alert_form = CreateAlertForm(initial={'alertText': query,
                                              'alertFrequency': "dly"})

    '''
    Code beyond this point will be run if the alert form failed, or if the 
    submission was a GET request. Beyond this point, we run the searches.
    '''
    search_form = SearchForm(request.GET)

    params = {}
    if search_form.is_valid():
        cd = search_form.cleaned_data

        # Build up all the queries needed
        params['q'] = cd['q']
        params['sort'] = request.GET.get('sort', '')
        params['facet'] = 'true'
        params['facet.mincount'] = 0
        params['facet.field'] = ['{!ex=dt}status_exact', '{!ex=dt}court_exact']
        selected_courts = [k.replace('court_', '')
                           for k, v in cd.iteritems()
                           if (k.startswith('court_') and v == True)]
        selected_courts = ' OR '.join(selected_courts)
        selected_stats = [k.replace('stat_', '')
                          for k, v in cd.iteritems()
                          if (k.startswith('stat_') and v == True)]
        selected_stats = ' OR '.join(selected_stats)
        fq = []
        if len(selected_courts) > 0:
            fq.append('{!tag=dt}court_exact:(%s)' % selected_courts)
        if len(selected_stats) > 0:
            fq.append('{!tag=dt}status_exact:(%s)' % selected_stats)
        if len(fq) > 0:
            params['fq'] = fq

        '''
        GOAL:
        http://localhost:8983/solr/select/?q=*:*&version=2.2&start=0&rows=0&indent=on&fq={!tag=dt}court_exact:%28ca1%20OR%20ca2%29&facet=true&facet.field={!ex=dt}court_exact&facet.field={!ex=dt}status_exact
        http://localhost:8983/solr/select/?
            q=*:*
            &version=2.2
            &start=0
            &rows=0
            &indent=on
            &fq={!tag=dt}court_exact:%28ca1%20OR%20ca2%29
            &facet=true
            &facet.field={!ex=dt}court_exact
            &facet.field={!ex=dt}status_exact
        '''
    else:
        print "The form is invalid or unbound."
        #TODO: Remove before sending live
        assert False
        params['q'] = '*'

    # Run the query
    print "Params sent to search are: %s" % params
    results_si = conn.raw_query(**params)
    facet_fields = results_si.execute().facet_counts.facet_fields
    print facet_fields

    # Merge the fields with the facet values and set up the form fields.
    # We need to handle two cases:
    #   1. The initial load of the page. For this we use the checked attr that 
    #      is set on the form if there isn't a sort order in the request.
    #   2. The load after form submission. For this, we use the field.value().
    # The other thing we're accomplishing here is to merge the fields from 
    # Django with the counts from Solr.
    court_facets = []
    court_list = dict(facet_fields['court_exact'])
    for field in search_form:
        try:
            count = court_list[field.html_name.replace('court_', '')]
        except KeyError:
            # Happens when a field is iterated on that doesn't exist in the 
            # facets variable
            continue

        try:
            refine = search_form['refine'].value()
        except KeyError:
            # Happens on page load, since the field doesn't exist yet.
            refine = 'new'

        if refine == 'new':
            checked = True
        else:
            # It's a refinement
            if field.value() == 'on':
                checked = True
            else:
                checked = False

        facet = [field.label,
                 field.html_name,
                 count,
                 checked]
        court_facets.append(facet)

    status_facets = []
    status_list = dict(facet_fields['status_exact'])
    for field in search_form:
        try:
            count = status_list[field.html_name.replace('stat_', '')]
        except KeyError:
            # Happens when a field is iterated on that doesn't exist in the 
            # facets variable
            continue

        try:
            refine = search_form['refine'].value()
        except KeyError:
            # Happens on page load, since the field doesn't exist yet.
            refine = 'new'

        if refine == 'new':
            checked = True
        else:
            print field.value()
            # It's a refinement
            if field.value() == 'on':
                checked = True
            else:
                checked = False

        facet = [field.label,
                 field.html_name,
                 count,
                 checked]
        status_facets.append(facet)

    # Finally, we make a copy of request.GET so it is mutable, and we make
    # some adjustments that we want to see in the rendered form.
    mutable_get = request.GET.copy()
    # Send the user the cleaned up query
    mutable_get['q'] = cd['q']
    # Always reset the radio box to refine
    mutable_get['refine'] = 'refine'
    search_form = SearchForm(mutable_get)

    # Set up pagination
    paginator = Paginator(results_si, 20)
    page = request.GET.get('page', 1)
    try:
        paged_results = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        paged_results = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        paged_results = paginator.page(paginator.num_pages)
    #print "alert.search.views facet_fields.facet_counts: %s" % facet_fields

    return render_to_response(
                  'search/search.html',
                  {'search_form': search_form, 'alert_form': alert_form,
                   'results': paged_results, 'court_facets': court_facets,
                   'status_facets': status_facets},
                  RequestContext(request))

    #############
    # SCRAPS
    #############
    #results_foo = results_si.execute()
    #print results_foo[0]['caseName']

    #                            &facet=true     facet.field=status_exact                      &q=court+-newell
    #                            &facet=true     facet.field=court_exact&facet.field=status_exact&q=court+-newell
    #facet_si = conn.raw_query(**{'facet':'true', 'facet.field':['court_exact', 'status_exact'], 'q':query}).execute()
    #print facet_si
    #facet_si = facet_si.facet_by('court_exact')
    #highlight_si = conn.query()
    #highlight_si = highlight_si.query(highlight_si.Q({'q':'court -newell'}))
    #INFO: [] webapp=/solr path=/select/ params={q=q} hits=35 status=0 QTime=1 

    #INFO: [] webapp=/solr path=/select/ params={q=court+-newell} hits=733 status=0 QTime=2 
    #INFO: [] webapp=/solr path=/select/ params={q=court\+\-newell} hits=0 status=0 QTime=1


    '''
    q_frags = query.split()
    results_si = conn.query(q_frags[0])
    facet_si = conn.query(q_frags[0])
    highlight_si = conn.query(q_frags[0])
    for frag in q_frags[1:]:
        results_si = results_si.query(frag)
        facet_si = facet_si.query(frag)
        highlight_si = highlight_si.query(frag)
    '''

    # Set up facet counts
    #facet_fields = {}
    #facet_fields = facet_si.facet_by('court_exact', mincount=1).facet_by('status_exact').execute().facet_counts.facet_fields

    # Set up highlighting
    #hl_results = highlight_si.highlight('text', snippets=5).highlight('status')\
    #    .highlight('caseName').highlight('westCite').highlight('docketNumber')\
    #    .highlight('lexisCite').highlight('westCite').execute()
    #import pprint
    #pprint.pprint(hl_results)

    '''
    results = []
    for result in results_si.execute():
        #type(result['id'])
        #results_si[result['id']]['highlighted_text'] = result.highlighting['text']
        #results_si[hl_results.highlighting['search.document.464']]['highlighted_text'] = 'foo'
        temp_dict = {}
        try:
            temp_dict['caseName'] = hl_results.highlighting[result['id']]['caseName'][0]
        except KeyError:
            temp_dict['caseName'] = result['caseName']
        try:
            temp_dict['text'] = hl_results.highlighting[result['id']]['text']
        except KeyError:
            # No highlighting in the text for this result. Just assign the 
            # default unhighlighted value
            temp_dict['text'] = result['text']

        results.append(temp_dict)
    '''

    '''
    Goal:
     [doc1: {caseName: 'foo', text: 'bar', status:'baz'}]
    '''

    '''
    for d in r:
        d['highlighted_name'] = r.highlighting[d['id']]['name']
    book_list = r
    '''


def tools_page(request):
    return render_to_response('tools.html', {}, RequestContext(request))

def browser_warning(request):
    return render_to_response('browser_warning.html', {}, RequestContext(request))
