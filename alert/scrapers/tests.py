import hashlib
import SimpleHTTPServer
import SocketServer
import threading


from datetime import date, timedelta
from django.conf import settings
from django.test import TestCase
from alert.lib import sunburnt
from alert.scrapers.DupChecker import DupChecker
from alert.scrapers.models import urlToHash
from alert.scrapers.scrape_and_extract import scrape_court
from alert.scrapers.test_assets import test_scraper
from alert.search.models import Court, Document
from juriscraper.GenericSite import GenericSite


PORT = 8080


class TestServer(SocketServer.TCPServer):
    allow_reuse_address = True


class SilentHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class SetupException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


class IngestionTest(TestCase):
    fixtures = ['test_court.json']

    def ingest_documents(self):
        site = test_scraper.Site().parse()
        scrape_court(site)

    @classmethod
    def setUpClass(cls):
        # Set up a simple server for the crawler to hit
        cls.httpd = TestServer(('', PORT), SilentHandler)
        httpd_thread = threading.Thread(target=cls.httpd.serve_forever)
        httpd_thread.daemon = True
        httpd_thread.start()

    def setUp(self):
        # Clear the Solr index
        self.si = sunburnt.SolrInterface(settings.SOLR_URL, mode='rw')
        if self.si.query(text='*:*').count() > 1000:
            raise SetupException('Solr has more than 1000 items. Will not empty as part of a test.')
        self.si.delete_all()

    def tearDown(self):
        # Clear the Solr index
        self.si.delete_all()

    def test_parsing_xml_document_to_site_object(self):
        site = test_scraper.Site().parse()
        self.assertEqual(len(site.case_names), 6)


    def test_content_extraction(self):
        #self.ingest_documents()
        pass

    def test_wpd_extraction(self):
        '''
        doc = Document.objects.get(local_path__endswith='wpd')
        extract_doc_content(doc.pk, callback=subtask(extract_by_ocr))
        self.assertIn('indiana', doc.html.lower())
        '''
        pass


    def test_doc_extraction(self):
        pass


    def test_pdf_extraction(self):
        pass

    def test_pdf_ocr_extraction(self):
        pass

    def test_html_extraction(self):
        pass

    def test_txt_extraction(self):
        pass


class DupcheckerTest(TestCase):
    fixtures = ['test_court.json']

    def setUp(self):
        self.court = Court.objects.get(pk='test')
        self.dup_checkers = [DupChecker(self.court, full_crawl=True),
                             DupChecker(self.court, full_crawl=False)]

    def test_abort_when_new_court_website(self):
        """Tests what happens when a new website is discovered."""
        site = test_scraper.Site()
        site.hash = 'this is a dummy hash code string'

        for dup_checker in self.dup_checkers:
            abort = dup_checker.abort_by_url_hash(site.url, site.hash)
            if dup_checker.full_crawl:
                self.assertFalse(abort, "DupChecker says to abort during a full crawl.")
            else:
                self.assertFalse(abort, "DupChecker says to abort on a court that's never been crawled before.")

            # The checking function creates url2Hashes, that we must delete as part of cleanup.
            dup_checker.url2Hash.delete()

    def test_abort_on_unchanged_court_website(self):
        """Similar to the above, but we create a url2hash object before checking if it exists."""
        site = test_scraper.Site()
        site.hash = 'this is a dummy hash code string'
        for dup_checker in self.dup_checkers:
            urlToHash(url=site.url, SHA1=site.hash).save()
            abort = dup_checker.abort_by_url_hash(site.url, site.hash)
            if dup_checker.full_crawl:
                self.assertFalse(abort, "DupChecker says to abort during a full crawl.")
            else:
                self.assertTrue(abort, "DupChecker says not to abort on a court that's been crawled before with the same hash")

            dup_checker.url2Hash.delete()

    def test_abort_on_changed_court_website(self):
        """Similar to the above, but we create a url2Hash with a different hash before checking if it exists."""
        site = test_scraper.Site()
        site.hash = 'this is a dummy hash code string'
        for dup_checker in self.dup_checkers:
            urlToHash(url=site.url, SHA1=site.hash).save()
            abort = dup_checker.abort_by_url_hash(site.url, "this is a *different* hash!")
            if dup_checker.full_crawl:
                self.assertFalse(abort, "DupChecker says to abort during a full crawl.")
            else:
                self.assertFalse(abort, "DupChecker says to abort on a court where the hash has changed.")

            dup_checker.url2Hash.delete()

    def test_should_we_continue_with_an_empty_database(self):
        for dup_checker in self.dup_checkers:
            onwards = dup_checker.should_we_continue('content', date.today(), date.today() - timedelta(days=1))
            if not dup_checker.full_crawl:
                self.assertTrue(onwards, "DupChecker says to abort during a full crawl.")
            else:
                count = Document.objects.all().count()
                self.assertTrue(onwards, "DupChecker says to abort on dups when the database has %s Documents." % count)

    def test_should_we_continue_with_a_dup_found(self):
        self.dup_checkers = [DupChecker(self.court, full_crawl=True, dup_threshold=0),
                             DupChecker(self.court, full_crawl=False, dup_threshold=0)]
        content = "this is dummy content that we hash"
        content_hash = hashlib.sha1(content).hexdigest()
        for dup_checker in self.dup_checkers:
            doc = Document(sha1=content_hash, court=self.court)
            doc.save()
            onwards = dup_checker.should_we_continue(content, date.today(), date.today())
            if dup_checker.full_crawl:
                self.assertTrue(onwards, "DupChecker says to abort during a full crawl.")
            else:
                self.assertFalse(onwards, "DupChecker says to continue but there should be a duplicate in the database. "
                                          "dup_count is %s, and dup_threshold is %s" % (dup_checker.dup_count,
                                                                                        dup_checker.dup_threshold))
            doc.delete()

    def test_should_we_continue_with_dup_found_and_older_date(self):
        content = "this is dummy content that we hash"
        content_hash = hashlib.sha1(content).hexdigest()
        for dup_checker in self.dup_checkers:
            doc = Document(sha1=content_hash, court=self.court)
            doc.save()
            # Note that the next case occurs prior to the current one
            onwards = dup_checker.should_we_continue(content, date.today(), date.today() - timedelta(days=1))
            if dup_checker.full_crawl:
                self.assertTrue(onwards, "DupChecker says to abort during a full crawl.")
            else:
                self.assertFalse(onwards, "DupChecker says to continue but there should be a duplicate in the database. "
                                          "dup_count is %s, and dup_threshold is %s" % (dup_checker.dup_count,
                                                                                        dup_checker.dup_threshold))
            doc.delete()
