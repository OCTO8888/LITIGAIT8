import sys
sys.path.append('/var/www/court-listener/alert')

import settings
from django.core.management import setup_environ
setup_environ(settings)

from alert.lib import magic
from alert.lib.string_utils import trunc
from alert.scrapers.models import urlToHash, ErrorLog
from alert.search.models import Citation
from alert.search.models import Court
from alert.search.models import Document

from celery.task.sets import subtask
from django.core.files.base import ContentFile
from juriscraper.GenericSite import logger
from juriscraper.lib.importer import build_module_list

# adding alert to the front of this breaks celery. Ignore pylint error.
from scrapers.tasks import extract_doc_content, extract_by_ocr

import hashlib
import mimetypes
import signal
import requests
import time
import traceback
from lxml import html
from optparse import OptionParser


# for use in catching the SIGINT (Ctrl+4)
die_now = False


def signal_handler(signal, frame):
    # Trigger this with CTRL+4
    logger.info('**************')
    logger.info('Signal caught. Finishing the current court, then exiting...')
    logger.info('**************')
    global die_now
    die_now = True


def court_changed(url, hash):
    """Determines whether a court website has changed since we last saw it.

    Takes a hash generated by Juriscraper and compares that hash to a value
    in the DB, if there is one. If there is a value and it is the same, it
    returns False. Else, it returns True.
    """
    url2Hash, created = urlToHash.objects.get_or_create(url=url)
    if not created and url2Hash.SHA1 == hash:
        # it wasn't created, and it has the same SHA --> not changed.
        return False, url2Hash
    else:
        # It's a known URL or it's a changed hash.
        return True, url2Hash


def _test_for_meta_redirections(r):
    mime = magic.from_buffer(r.content, mime=True)
    extension = mimetypes.guess_extension(mime)
    if extension == '.html':
        html_tree = html.fromstring(r.text)
        try:
            attr = html_tree.xpath("//meta[translate(@http-equiv, 'REFSH', 'refsh') = 'refresh']/@content")[0]
            wait, text = attr.split(";")
            if text.lower().startswith("url="):
                url = text[4:]
                return True, url
        except IndexError:
            return False, None
    else:
        return False, None


def follow_redirections(r, s):
    """
    Recursive function that follows meta refresh redirections if they exist.
    """
    redirected, url = _test_for_meta_redirections(r)
    if redirected:
        logger.info('Following a meta redirection to: %s' % url)
        r = follow_redirections(s.get(url), s)
    return r


def scrape_court(site, full_crawl=False):
    download_error = False
    # Get the court object early for logging
    # opinions.united_states.federal.ca9_u --> ca9
    court_str = site.court_id.split('.')[-1].split('_')[0]
    court = Court.objects.get(courtUUID=court_str)

    if not full_crawl:
        changed, url2Hash = court_changed(site.url, site.hash)
        if not changed:
            logger.info("Unchanged hash at: %s" % site.url)
            return
        else:
            logger.info("Identified changed hash at: %s" % site.url)

    dup_count = 0
    for i in range(0, len(site.case_names)):
        try:
            url = site.download_urls[i]
            if not url:
                # Occurs when a DeferredList fetcher fails.
                continue
            s = requests.session()
            r = s.get(url)

            # test for empty files (thank you CA1)
            if len(r.content) == 0:
                msg = 'EmptyFileError: %s\n%s' % (url,
                                                  traceback.format_exc())
                logger.warn(msg)
                ErrorLog(log_level='WARNING', court=court, message=msg).save()
                continue

            # test for and follow meta redirects
            r = follow_redirections(r, s)
        except:
            msg = 'DownloadingError: %s\n%s' % (url,
                                                traceback.format_exc())
            logger.warn(msg)
            ErrorLog(log_level='WARNING', court=court, message=msg).save()
            continue

        # Make a hash of the file
        sha1_hash = hashlib.sha1(r.content).hexdigest()

        # using the hash, check for a duplicate in the db.
        exists = Document.objects.filter(documentSHA1=sha1_hash).exists()

        # If the doc is a dup, increment the dup_count variable and set the
        # dup_found_date
        if exists:
            logger.info('Duplicate found at: %s' % site.download_urls[i])

            if not full_crawl:
                dup_found_date = site.case_dates[i]
                dup_count += 1

                # If we found a dup on dup_found_date, then we can exit before
                # parsing any prior dates.
                try:
                    already_scraped_next_date = (site.case_dates[i + 1] < dup_found_date)
                except IndexError:
                    already_scraped_next_date = True
                if already_scraped_next_date:
                    if court_str != 'mich':
                        # Michigan sometimes has multiple occurrences of the
                        # same case with different dates on a page.
                        logger.info('Next case occurs prior to when we found a '
                                    'duplicate. Court is up to date.')
                        url2Hash.SHA1 = site.hash
                        url2Hash.save()
                        return
                elif dup_count >= 5:
                    logger.info('Found five duplicates in a row. Court is up to date.')
                    url2Hash.SHA1 = site.hash
                    url2Hash.save()
                    return
                else:
                    # Not the fifth duplicate. Continue onwards.
                    continue
            else:
                # This is a full crawl with no dup aborting.
                continue

        else:
            # Not a duplicate; proceed...
            logger.info('Adding new document found at: %s' % site.download_urls[i])
            dup_count = 0

            # Make a citation
            cite = Citation(case_name=site.case_names[i])
            if site.docket_numbers is not None:
                cite.docketNumber = site.docket_numbers[i]
            if site.neutral_citations is not None:
                cite.neutral_cite = site.neutral_citations[i]

            # Make the document object
            doc = Document(source='C',
                           documentSHA1=sha1_hash,
                           dateFiled=site.case_dates[i],
                           court=court,
                           download_URL=site.download_urls[i],
                           documentType=site.precedential_statuses[i])

            # Make and associate the file object
            try:
                cf = ContentFile(r.content)
                mime = magic.from_buffer(r.content, mime=True)
                if mime is None:
                    # Workaround for issue with libmagic1==5.09-2 in Ubuntu 12.04. Fixed in libmagic 5.11-2.
                    file_str = magic.from_buffer(r.content)
                    if file_str.startswith('Composite Document File V2 Document'):
                        mime = 'application/msword'
                extension = mimetypes.guess_extension(mime)
                if extension == '.obj':
                    # It's actually a wpd
                    extension = '.wpd'
                # See issue #215 for why this must be lower-cased.
                file_name = trunc(site.case_names[i].lower(), 75) + extension
                doc.local_path.save(file_name, cf, save=False)
            except:
                msg = 'Unable to save binary to disk. Deleted document: % s.\n % s' % \
                        (cite.case_name, traceback.format_exc())
                logger.critical(msg)
                ErrorLog(log_level='CRITICAL', court=court, message=msg).save()
                download_error = True
                continue

            # Save everything, but don't update Solr index yet
            cite.save(index=False)
            doc.citation = cite
            doc.save(index=False)

            # Extract the contents asynchronously.
            extract_doc_content(doc.pk, callback=subtask(extract_by_ocr))

            logger.info("Successfully added: %s" % site.case_names[i])

    # Update the hash if everything finishes properly.
    logger.info("%s: Successfully crawled." % site.court_id)
    if not download_error and not full_crawl:
        # Only update the hash if no errors occurred.
        url2Hash.SHA1 = site.hash
        url2Hash.save()


def main():
    global die_now

    # this line is used for handling SIGTERM (CTRL+4), so things can die safely
    signal.signal(signal.SIGTERM, signal_handler)

    usage = 'usage: %prog -c COURTID [-d] [-r RATE]'
    parser = OptionParser(usage)
    parser.add_option('-d', '--daemon', action="store_true", dest='daemonmode',
                      default=False, help=('Use this flag to turn on daemon '
                                           'mode, in which all courts requested '
                                           'will be scraped in turn, non-stop.'))
    parser.add_option('-r', '--rate', dest='rate', metavar='RATE',
                      help=('The length of time in minutes it takes to crawl all '
                            'requested courts. Particularly useful if it is desired '
                            'to quickly scrape over all courts. Default is 30 '
                            'minutes.'))
    parser.add_option('-c', '--courts', dest='court_id', metavar="COURTID",
                      help=('The court(s) to scrape and extract. This should be in '
                            'the form of a python module or package import '
                            'from the Juriscraper library, e.g. '
                            '"juriscraper.opinions.united_states.federal.ca1" or '
                            'simply "opinions" to do all opinions.'))
    parser.add_option('-f', '--fullcrawl', dest='full_crawl',
                      action='store_true',
                      help="Disable duplicate aborting.")
    (options, args) = parser.parse_args()

    daemon_mode = options.daemonmode
    court_id = options.court_id
    full_crawl = options.full_crawl

    try:
        rate = int(options.rate)
    except (ValueError, AttributeError, TypeError):
        rate = 30

    if not court_id:
        parser.error('You must specify a court as a package or module.')
    else:
        module_strings = build_module_list(court_id)
        if len(module_strings) == 0:
            parser.error('Unable to import module or package. Aborting.')

        logger.info("Starting up the scraper.")
        num_courts = len(module_strings)
        wait = (rate * 60) / num_courts
        i = 0
        while i < num_courts:
            # this catches SIGINT, so the code can be killed safely.
            if die_now:
                logger.info("The scraper has stopped.")
                sys.exit(1)

            package, module = module_strings[i].rsplit('.', 1)

            mod = __import__("%s.%s" % (package, module),
                             globals(),
                             locals(),
                             [module])

            try:
                site = mod.Site().parse()
                scrape_court(site, full_crawl)
            except:
                msg = ('********!! CRAWLER DOWN !!***********\n'
                       '*****scrape_court method failed!*****\n'
                       '********!! ACTION NEEDED !!**********\n%s') % \
                       traceback.format_exc()
                logger.critical(msg)

                # opinions.united_states.federal.ca9_u --> ca9
                court_str = mod.Site.__module__.split('.')[-1].split('_')[0]
                court = Court.objects.get(courtUUID=court_str)
                ErrorLog(log_level='CRITICAL', court=court, message=msg).save()
                i += 1
                continue

            time.sleep(wait)
            last_court_in_list = (i == (num_courts - 1))
            if last_court_in_list and daemon_mode:
                i = 0
            else:
                i += 1

    logger.info("The scraper has stopped.")
    sys.exit(0)

if __name__ == '__main__':
    main()
