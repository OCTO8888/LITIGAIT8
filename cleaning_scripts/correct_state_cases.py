import sys
sys.path.append('/var/www/court-listener/alert')

import settings
from celery.task.sets import subtask
from django.core.management import setup_environ
setup_environ(settings)

from search.models import Document, Court
from alert.lib.db_tools import queryset_generator
from optparse import OptionParser

# adding alert to the front of this breaks celery. Ignore pylint error.
from scrapers.tasks import extract_doc_content, extract_by_ocr

def fixer(simulate=False, verbose=False):
    '''Fix a few issues discovered.'''
    #docs = queryset_generator(Document.objects.filter(source='C', documentPlainText=''))
    #docs = Document.objects.raw('''select "documentUUID"  from "Document" where "source" = 'C' and "documentPlainText" ~ '^[[:space:]]*$' ''')
    #docs = Document.objects.raw('''select "documentUUID" from "Document" where "source" = 'C' and "documentPlainText" = 'Unable to extract document content.' ''')

    def fix_plaintiffs(docs, left, simulate, verbose):
        for doc in docs:
            if verbose:
                print "Fixing document number %s: %s" % (doc.pk, doc)
                old_case_name = doc.citation.case_name
                if left:
                    new_case_name = old_case_name.replace('P. v.', 'People v.')
                else:
                    new_case_name = old_case_name.replace('v. P.', 'v. People')
                print "    Replacing %s" % old_case_name
                print "         with %s" % new_case_name

            if not simulate:
                if left:
                    doc.citation.case_name = doc.citation.case_name.replace('P. v.', 'People v.')
                else:
                    doc.citation.case_name = doc.citation.case_name.replace('v. P.', 'v. People')
                doc.save()

    def fix_michigan(docs, left, simulate, verbose):
        for doc in docs:
            if verbose:
                print "Fixing document number %s: %s" % (doc.pk, doc)
                old_case_name = doc.citation.case_name
                if left:
                    new_case_name = old_case_name.replace('Mi ', 'Michigan ')
                else:
                    new_case_name = old_case_name.replace(' Mi', ' Michigan')
                print "    Replacing %s" % old_case_name
                print "         with %s" % new_case_name

            if not simulate:
                if left:
                    doc.citation.case_name = doc.citation.case_name.replace('Mi ', 'Michigan ')
                else:
                    doc.citation.case_name = doc.citation.case_name.replace(' Mi', ' Michigan')

    def fix_wva(docs, simulate, verbose):
        for doc in docs:
            if verbose:
                print "Fixing document number %s: %s" % (doc.pk, doc)
            if not simulate:
                doc.documentType = "Published"
                doc.save()


    # Round one! Fix plaintiffs.
    court = Court.objects.get(courtUUID='cal')
    docs = queryset_generator(Document.objects.filter(source="C", court=court, citation__case_name__contains=('P. v.')))
    fix_plaintiffs(docs, True, simulate, verbose)

    # Round two! Fix appellants.
    docs = queryset_generator(Document.objects.filter(source="C", court=court, citation__case_name__contains=('v. P.')))
    fix_plaintiffs(docs, False, simulate, verbose)

    # Round three! Fix the Mi cases.
    court = Court.objects.get(courtUUID='mich')
    docs = queryset_generator(Document.objects.filter(source="C", court=court, citation__case_name__contains=('Mi %')))
    fix_michigan(docs, True, simulate, verbose)

    # Round four! Fix the other Mi cases.
    docs = queryset_generator(Document.objects.filter(source="C", court=court, citation__case_name__contains=('% Mi')))
    fix_michigan(docs, False, simulate, verbose)

    # Round five! Fix the statuses.
    court = Court.objects.get(courtUUID='wva')
    docs = queryset_generator(Document.objects.filter(documentType__in=['Memorandum Decision', 'Per Curiam Opinion', 'Signed Opinion'],
                                                      court=court))
    fix_wva(docs, simulate, verbose)



def main():
    usage = "usage: %prog [--verbose] [---simulate]"
    parser = OptionParser(usage)
    parser.add_option('-v', '--verbose', action="store_true", dest='verbose',
        default=False, help="Display log during execution")
    parser.add_option('-s', '--simulate', action="store_true",
        dest='simulate', default=False, help=("Simulate the corrections without "
        "actually making them."))
    (options, args) = parser.parse_args()

    verbose = options.verbose
    simulate = options.simulate

    if simulate:
        print "*******************************************"
        print "* SIMULATE MODE - NO CHANGES WILL BE MADE *"
        print "*******************************************"

    return fixer(simulate, verbose)
    exit(0)

if __name__ == '__main__':
    main()
