# !/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import re

from eyecite.find_citations import get_citations

from cl.lib.command_utils import VerboseCommand, logger
from cl.lib.string_utils import normalize_dashes
from cl.search.models import Citation, OpinionCluster


def get_tax_docket_numbers(opinion_text):
    """
    Parse opinon plain text for docket numbers.

    First we idenitify where the docket numbers are in the document.
    This is normally at the start of the document but can often follow
     a lengthy case details section.

    :param opinion_text: is the opinions plain_text
    :return docket_string: as string of docket numbers Ex. (18710-94, 12321-95)
    """
    opinion_text = normalize_dashes(opinion_text)
    parsed_text = ""
    docket_no_re = r"Docket.? Nos?.? .*[0-9]{3,5}"
    matches = re.finditer(docket_no_re, opinion_text)

    for matchNum, match in enumerate(matches, start=1):
        parsed_text = opinion_text[match.start() :]
        break

    matches2 = re.finditer(
        r"[0-9]{3,5}(-|–)[\w]{2,4}([A-Z])?((\.)| [A-Z]\.)", parsed_text
    )
    for m2, match2 in enumerate(matches2, start=0):
        parsed_text = parsed_text[: match2.end()]
        break

    docket_end_re = r"[0-9]{3,5}(-|–)[\w]{2,4}([A-Z])?((\,|\.)| [A-Z]\.)"

    matches = re.finditer(docket_end_re, parsed_text, re.MULTILINE)
    hits = []
    for matchNum, match in enumerate(matches, start=1):
        hits.append(match.group())
    docket_string = ", ".join(hits).replace(",,", ",").replace(".", "")
    return docket_string.strip()


def find_tax_court_citation(opinion_text):
    """
    Returns a dictionary representation of our
    Citation object.

    Return the citation object or nothing.
    Iterates over lines of text beacuse we assume our citations won't wrap.

    :param opinion_text: The plain_text of our opinion from the scrape.
    :return: citation object or None
    """
    for line_of_text in opinion_text.split("\n")[:250]:
        cites = get_citations(line_of_text)
        if not cites:
            continue

        if "UNITED STATES TAX COURT REPORT" in opinion_text:
            for cite in cites:
                if "UNITED STATES TAX COURT REPORT" in cite.reporter_found:
                    cite.type = Citation.SPECIALTY
                    return cite
        else:
            for cite in cites:
                if (
                    "T.C." not in cite.reporter
                    and "T. C." not in cite.reporter
                ):
                    # If not the first cite - Skip
                    return None

                if cite.reporter_index > 2:
                    # If reporter not in first or second term in the line we skip.
                    return None

                alt_cite = line_of_text.replace(
                    cite.reporter_found, ""
                ).strip()
                other_words = alt_cite.split(" ")

                if len([x for x in other_words if x != ""]) > 3:
                    # If line has more than three non reporter components skip.
                    return None

                if "T.C." == cite.reporter:
                    cite_type = Citation.SPECIALTY
                elif "T.C. No." == cite.reporter:
                    cite_type = Citation.SPECIALTY
                else:
                    cite_type = Citation.NEUTRAL

                cite.type = cite_type
                return cite


def fix_precedential_status(options):
    """
    This code corrects an on-going issues with scraping cases from tax court.

    T.C. Memo(randum) cases are all being set to precedential when they should
    not be. We can identify those cases by checking the citation type.

    :param options:
    :return: None
    """
    logger.info("Starting cleanup.")
    ocs = OpinionCluster.objects.filter(
        docket__court="tax", precedential_status="Published"
    )
    for oc in ocs:
        if oc.citations.filter(type=Citation.NEUTRAL).exists():
            logger.info("Updating cluster %s ", oc)
            oc.precedential_status = "Unpublished"
            oc.save()

    logger.info("Finished cleanup.")


def update_tax_opinions(options):
    """
    This code identifies tax opinions without
    docket numbers or citations and attempts to parse them out
    and add the citation and docket numbers to the case.

    http://www.ustaxcourt.gov/UstcInOp/asp/Todays.asp is an identifier for
    bad scrapes in tax court.
    :return: None
    """
    logger.info("Start updating Tax Opinions")
    ocs = OpinionCluster.objects.filter(docket__court="tax").filter(
        docket__docket_number=None
    )

    # We had a number of failed scrapes and the bad_url helps identify them
    bad_url = "http://www.ustaxcourt.gov/UstcInOp/asp/Todays.asp"
    for oc in ocs:
        op_objs = oc.sub_opinions.all()
        for opinion in op_objs:
            if opinion.plain_text == "":
                logger.info("No plain text to parse.")
                continue
            if opinion.download_url == bad_url:
                logger.info("Failed scrape, nothing to parse.")
                continue

            docket_numbers = get_tax_docket_numbers(opinion.plain_text)
            if docket_numbers:
                logger.info(
                    "Adding Docket Numbers: %s to %s"
                    % (docket_numbers, oc.docket.case_name)
                )
                oc.docket.docket_number = docket_numbers
                oc.docket.save()

            cite = find_tax_court_citation(opinion.plain_text)

            if cite is None:
                logger.info(
                    "No cite to add for opinion %s on cluster %s"
                    % (opinion.id, oc.id)
                )
                continue

            if Citation.objects.filter(
                volume=cite.volume,
                reporter=cite.reporter,
                page=cite.page,
                cluster_id=oc.id,
            ).exists():
                logger.info("Citation already in the system. Return None.")
                continue

            logger.info(
                "Saving citation %s %s %s"
                % (cite.volume, cite.reporter, cite.page)
            )

            Citation.objects.get_or_create(
                volume=cite.volume,
                reporter=cite.reporter,
                page=cite.page,
                type=cite.type,
                cluster_id=oc.id,
            )


def find_missing_or_incorrect_citations(options):
    """Iterate over tax cases to verify which citations are correctly parsed

    This code should pull back all the cases with plaintext tax courts to parse.
    Iterate over those cases extracting the citation if any

    :param options:
    :return:
    """
    should_fix = options["fix"]

    ocs = OpinionCluster.objects.filter(docket__court="tax").exclude(
        sub_opinions__plain_text=""
    )
    logger.info("%s clusters found", ocs.count())

    for oc in ocs:
        logger.warning(
            "Reference url: https://www.courtlistener.com/opinion/%s/x", oc.id
        )
        cites = oc.citations.all()

        logger.info("Found %s cite(s) for case in db", cites.count())

        if cites.count() > 0:
            if should_fix:
                logger.warning("Deleting cites in cluster %s", oc.id)
                cites.delete()

        ops = oc.sub_opinions.all()
        assert ops.count() == 1
        for op in ops:
            # Only loop over the first opinion because
            # these cases should only one have one opinion
            found_cite = find_tax_court_citation(op.plain_text)
            if found_cite is not None:
                found_cite_str = found_cite.base_citation()
                logger.info(
                    "Found citation in plain text as %s", found_cite_str
                )
                if should_fix:
                    logger.warning("Creating citation: %s", found_cite_str)
                    Citation.objects.create(
                        volume=found_cite.volume,
                        reporter=found_cite.reporter,
                        page=found_cite.page,
                        type=found_cite.type,
                        cluster_id=oc.id,
                    )
                else:
                    if cites.count() > 0:
                        for cite in cites:
                            if str(cite) != found_cite_str:
                                logger.warning(
                                    "Have (%s), Expect (%s)",
                                    cite,
                                    found_cite_str,
                                )
                    else:
                        logger.warning("Add %s to db", found_cite_str)

            else:
                if cites.count() > 0:
                    for cite in cites:
                        logger.warning("Have (%s), Expect None", cite)
                        logger.warning("%s should be removed", cite)
                else:
                    logger.info("No citation in db or text: %s", oc.id)


def find_missing_or_incorrect_docket_numbers(options):
    """Iterate over tax cases to verify which docket numbers are correct.

    :param options:
    :return: Nothing
    """

    should_fix = options["fix"]
    ocs = OpinionCluster.objects.filter(docket__court="tax").exclude(
        sub_opinions__plain_text=""
    )

    logger.info("%s clusters found", ocs.count())

    for oc in ocs:
        logger.info("Analyzing cluster %s", oc.id)
        ops = oc.sub_opinions.all()
        assert ops.count() == 1
        for op in ops:
            logger.warning(
                "Reference url: https://www.courtlistener.com/opinion/%s/x",
                oc.id,
            )
            # Only loop over the first opinion because these
            # cases should only one have one
            # because they were extracted from the tax courts
            dockets_in_db = oc.docket.docket_number.strip()
            found_dockets = get_tax_docket_numbers(op.plain_text)
            if found_dockets == dockets_in_db:
                if (
                    oc.docket.docket_number.strip() == ""
                    and dockets_in_db == ""
                ):
                    logger.info("No docket numbers found in db or text.")
                else:
                    logger.info("Docket numbers appear correct.")
                continue
            else:
                if dockets_in_db == "":
                    logger.warning(
                        "Docket No(s). found for the first time: %s",
                        found_dockets,
                    )
                elif found_dockets == "":
                    logger.warning(
                        "Docket No(s). not found in text but Docket No(s). %s in db",
                        dockets_in_db,
                    )
                else:
                    logger.warning(
                        "Dockets in db (%s) != (%s) docket parsed from text",
                        dockets_in_db,
                        found_dockets,
                    )
                if should_fix:
                    oc.docket.docket_number = found_dockets
                    oc.docket.save()


class Command(VerboseCommand):
    help = (
        "Update scraped Tax Court opinions. "
        "Add citation and docket numbers."
    )

    def valid_actions(self, s):
        if s.lower() not in self.VALID_ACTIONS:
            raise argparse.ArgumentTypeError(
                "Unable to parse action. Valid actions are: %s"
                % (", ".join(self.VALID_ACTIONS.keys()))
            )
        return self.VALID_ACTIONS[s]

    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=self.valid_actions,
            required=True,
            help="The action you wish to take. Valid choices are: %s"
            % (", ".join(self.VALID_ACTIONS.keys())),
        )
        parser.add_argument("--fix", action="store_true")

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)
        options["action"](options)

    VALID_ACTIONS = {
        "update-tax-opinions": update_tax_opinions,
        "find-failures": find_missing_or_incorrect_citations,
        "find-docket-numbers": find_missing_or_incorrect_docket_numbers,
        "fix-p-status": fix_precedential_status,
    }
