import networkx as nx
import logging

from scripts.wikilanggraph import generate_lang_graph, calculate_dissimilarity_metrics
from scripts.wikilanggraph import initialize_graph
from scripts.wikilanggraph import initialize_starting_page
from scripts.wikilanggraph.wikipedia_page import RevisionKey, Page


class Model:
    def __init__(self):
        self.network = None
        self.metrics = None
        self.df = None
        self.timestamps = None

    """
    this method should return:
    - a network representing article and links (for all available languages)
    - a pandas dataframe containing information on consecutive nodes of network: title, language, short fragment,
    is node a backlink, is node right-sided (is a language version)
    - a list of available moments in time for analysis of previous versions
    """

    async def get_article_data(self, article_name, article_language='en', moment_in_time=0, use_backlinks=False):
        languages = None

        graph: nx.Graph = initialize_graph()
        starting_page: Page = initialize_starting_page(
            language=article_language, title=article_name
        )
        graph: nx.Graph = await generate_lang_graph(
            graph=graph, starting_page=starting_page, languages=languages
        )
        metrics = calculate_dissimilarity_metrics(graph=graph)
        timestamps = starting_page.timepoints_all_languages

        logging.info("Graph: \n %s", nx.info(graph))
        logging.info("Metrics: \n %s", metrics.to_string())
        logging.info("Timestamps: %s", timestamps)

        self.metrics = metrics
        self.timestamps = timestamps

        temp_timestamp: RevisionKey = timestamps[moment_in_time]
        temp_graph = initialize_graph()
        page = Page(
            language=temp_timestamp.language,
            title=temp_timestamp.title,
            revision=temp_timestamp.oldid,
            timestamp=temp_timestamp.timestamp,
        )
        logging.debug("Backlinks: %s", starting_page._backlinks)
        # TODO finish revisions
        # temp_graph = await generate_lang_graph(
        #     graph=temp_graph, starting_page=page, languages=languages
        # )
        self.network = graph

    async def is_page_exising(self, article_name, article_language='en'):
        starting_page: Page = initialize_starting_page(
            language=article_language, title=article_name
        )
        return starting_page is None
