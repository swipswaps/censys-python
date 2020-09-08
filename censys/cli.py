#!/usr/bin/env python
"""
Interact with the Censys API through the command line.
"""

import os
import csv
import time
import json
import argparse
from typing import Union, List

from censys.ipv4 import CensysIPv4
from censys.websites import CensysWebsites
from censys.certificates import CensysCertificates
from censys.exceptions import CensysCLIException

Fields = List[str]
Results = List[dict]
Index = Union[CensysIPv4, CensysWebsites, CensysCertificates]


class CensysAPISearch:
    """
    This class searches the Censys API, taking in options from the command line and
    returning the results to a CSV or JSON file, or to stdout.

    Kwargs:
        format (str): What format to write the results. CSV, JSON, or stdout.
        start_page (int): What page the query should start from.
        max_pages (int): Adjust the number of results returned by the API.
        censys_api_secret (str): The API secret provided by Censys.
        censys_api_id (str): The API id provided by Censys.
    """

    csv_fields: Fields = list()
    """A list of fields to be used by the CSV writer."""

    def __init__(self, **kwargs):
        self.api_user = kwargs.get("censys_api_id")
        self.api_pass = kwargs.get("censys_api_secret")

        self.output_format = kwargs.get("format", "json")
        self.start_page = kwargs.get("start_page", 1)
        self.max_pages = kwargs.get("max_pages", 10)

    @staticmethod
    def _write_csv(filename: str, search_results: Results, fields: Fields) -> bool:
        """
        This method writes the search results to a new file in CSV format.

        Args:
            filename (str): The name of the file to write to on the disk.
            search_results (Results): A list of search results from an API query.
            fields (Fields): A list of fields to write as headers.

        Returns:
            bool: True if wrote to file successfully.
        """

        with open(filename, "w") as output_file:
            if search_results and isinstance(search_results, list):
                # Get the header row from the first result
                writer = csv.DictWriter(output_file, fieldnames=fields)
                writer.writeheader()

                for result in search_results:
                    # Use the Dict writer to process and write results to CSV
                    writer.writerow(result)

        print("Wrote results to file {}".format(filename))

        # method returns True, if the file has been written successfully.
        return True

    @staticmethod
    def _write_json(filename: str, search_results: Results) -> bool:
        """
        This method writes the search results to a new file in JSON format.

        Args:
            filename (str): name of the file to write to on the disk.
            search_results (Results): list of search results from API query.

        Returns:
            bool: True if wrote to file successfully.
        """

        with open(filename, "w") as output_file:
            # Since the results are already in JSON, just write them to a file.
            json.dump(search_results, output_file, indent=4)

        print("Wrote results to file {}".format(filename))
        return True

    @staticmethod
    def _write_screen(search_results: Results) -> bool:
        """
        This method writes the search results to screen.

        Args:
            search_results (Results): list of search results from API query.

        Returns:
            bool: True if wrote to file successfully.
        """

        print(json.dumps(search_results, indent=4))
        return True

    def write_file(self, results_list: Results) -> bool:
        """
        This method just sorts which format will be used to store
        the results of the query.

        Args:
            results_list: Is a list of results from the API query.

        Returns:
            bool: True if wrote out successfully.
        """

        # This method just creates some dynamic file names
        file_name_ext = "{}.{}".format(time.time(), self.output_format)
        filename = "{}.{}".format("censys-query-output", file_name_ext)

        if self.output_format == "csv":
            return self._write_csv(filename, results_list, fields=self.csv_fields)
        if self.output_format == "json":
            return self._write_json(filename, results_list)
        return self._write_screen(results_list)

    def _combine_fields(
        self, default_fields: Fields, user_fields: Fields, overwrite: bool = False,
    ) -> Fields:
        """
        This method is used to combine, or exclude fields depending on what
        the user has requested.

        Args:
            default_fields (Fields): A list of fields that are returned by default.
            user_fields (Fields): A list of user provided fields.
            overwrite (bool, optional): Overwrite the default list of fields with the
                                        given fields. Defaults to False.

        Raises:
            CensysCLIException: Too many fields specified.

        Returns:
            Fields: A list of fields.
        """

        field_list: Fields = default_fields

        if user_fields:
            if overwrite:
                field_list = user_fields
            else:
                field_list = list(set(user_fields + default_fields))

        # This is the hard limit for the number of fields that can be in a query.
        if len(list(field_list)) > 20:
            raise CensysCLIException(
                "Too many fields specified. The maximum number of fields is 20."
            )

        self.csv_fields = list(field_list)
        return list(field_list)

    def _process_search(
        self, query: str, search_index: Index, fields: Fields
    ) -> Results:
        """
        This method provides a common way to process searches from the API.

        Args:
            query: The string to send to the API as a query.
            search_index: The data set to be queried - IPv4, Website, or Certificates.
            fields: A list of fields that should be returned.

        Returns:
            Results: A list of search results from an API query.
        """

        records = []

        while True:
            response = search_index.paged_search(
                query=query, fields=fields, page=self.start_page
            )

            for record in response["results"]:
                records.append(record)

            # Break while loop when last page is reached
            if (
                response["metadata"]["page"] >= response["metadata"]["pages"]
                or response["metadata"]["page"] >= self.max_pages
            ):
                break

            self.start_page += 1

        return records

    def search_ipv4(self, **kwargs) -> Results:
        """
        A method to search the IPv4 data set via the API.

        Args:
            kwargs:
                query: The string search query.
                fields: The fields that should be returned with a query.
                overwrite: Overwrite the default list of fields with the given fields.

        Returns:
            Results: A list of search results from an API query.
        """

        default_fields = [
            "updated_at",
            "protocols",
            "metadata.description",
            "autonomous_system.name",
            "23.telnet.banner.banner",
            "80.http.get.title",
            "80.http.get.metadata.description",
            "8080.http.get.metadata.description",
            "8888.http.get.metadata.description",
            "443.https.get.metadata.description",
            "443.https.get.title",
            "443.https.tls.certificate.parsed.subject_dn",
            "443.https.tls.certificate.parsed.names",
            "443.https.tls.certificate.parsed.subject.common_name",
            "443.https.tls.certificate.parsed.extensions.subject_alt_name.dns_names",
        ]

        query = kwargs.get("query", "")
        fields = kwargs.get("fields", [])
        overwrite = kwargs.get("overwrite", False)

        index = CensysIPv4(api_id=self.api_user, api_secret=self.api_pass)

        return self._process_search(
            query,
            index,
            self._combine_fields(default_fields, fields, overwrite=overwrite),
        )

    def search_certificates(self, **kwargs) -> Results:
        """
        A method to search the Certificates data set via the API.

        Args:
            kwargs:
                query: The string search query.
                fields: The fields that should be returned with a query.
                overwrite: Overwrite the default list of fields with the given fields.

        Returns:
            Results: A list of search results from an API query.
        """

        default_fields = [
            "metadata.updated_at",
            "parsed.issuer.common_name",
            "parsed.names",
            "parsed.serial_number",
            "parsed.self_signed",
            "parsed.subject.common_name",
            "parsed.validity.start",
            "parsed.validity.end",
            "parsed.validity.length",
            "metadata.source",
            "metadata.seen_in_scan",
            "tags",
        ]

        query = kwargs.get("query", "")
        fields = kwargs.get("fields", [])
        overwrite = kwargs.get("overwrite", False)

        index = CensysCertificates(api_id=self.api_user, api_secret=self.api_pass)

        return self._process_search(
            query,
            index,
            self._combine_fields(default_fields, fields, overwrite=overwrite),
        )

    def search_websites(self, **kwargs) -> Results:
        """A method to search the Websites (Alexa Top 1M) data set via the API

        Args:
            kwargs:
                query: The string search query.
                fields: The fields that should be returned with a query.
                overwrite: Overwrite the default list of fields with the given fields.

        Returns:
            Results: A list of search results from an API query.
        """

        default_fields = [
            "443.https.tls.version",
            "alexa_rank",
            "domain",
            "ports",
            "protocols",
            "tags",
            "updated_at",
        ]

        query = kwargs.get("query", "")
        fields = kwargs.get("fields", [])
        overwrite = kwargs.get("overwrite", False)

        index = CensysWebsites(api_id=self.api_user, api_secret=self.api_pass)

        return self._process_search(
            query,
            index,
            self._combine_fields(default_fields, fields, overwrite=overwrite),
        )


def main():
    """main cli function"""

    def formatter(prog):
        return argparse.HelpFormatter(prog, max_help_position=50, width=100)

    parser = argparse.ArgumentParser(
        description="Query Censys Search via the command line",
        formatter_class=formatter,
    )

    parser.add_argument("query", type=str)
    parser.add_argument(
        "--query-type",
        type=str,
        default="ipv4",
        choices=["ipv4", "certs", "websites"],
        metavar="ipv4|certs|websites",
    )
    parser.add_argument(
        "--fields", nargs="+", help="list of fields seperated by a space"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="overwrite instead of append the default fields \
            with the given list of fields",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="screen",
        metavar="json|csv|screen",
        help="format of output",
    )
    parser.add_argument("--start-page", default=1, type=int, help="start page number")
    parser.add_argument("--max-pages", default=1, type=int, help="max number of pages")
    parser.add_argument(
        "--censys-api-id",
        default=os.getenv("CENSYS_API_ID"),
        required=False,
        help="provide a Censys API ID \
            (alternatively you can use the env variable CENSYS_API_ID)",
    )
    parser.add_argument(
        "--censys-api-secret",
        default=os.getenv("CENSYS_API_SECRET"),
        required=False,
        help="provide a Censys API SECRET \
            (alternatively you can use the env variable CENSYS_API_SECRET)",
    )

    args = parser.parse_args()

    censys_args = {"query": args.query}

    if args.fields:
        censys_args["fields"] = args.fields

    if args.output:
        censys_args["format"] = args.output

    if args.start_page:
        censys_args["start_page"] = args.start_page

    if args.max_pages:
        censys_args["max_pages"] = args.max_pages

    if args.censys_api_id:
        censys_args["censys_api_id"] = args.censys_api_id

    if args.censys_api_secret:
        censys_args["censys_api_secret"] = args.censys_api_secret

    if args.overwrite:
        censys_args["overwrite"] = args.overwrite

    censys = CensysAPISearch(**censys_args)

    indexes = {
        "ipv4": censys.search_ipv4,
        "certs": censys.search_certificates,
        "websites": censys.search_websites,
    }

    func = indexes[args.query_type]
    results = func(**censys_args)

    try:
        censys.write_file(results)
    except ValueError as error:  # pragma: no cover
        print("Error writing log file. Error: {}".format(error))


if __name__ == "__main__":  # pragma: no cover
    main()
