import logging
import random

import networkx as nx

right_node_count = 50
left_node_count = 3


class ViewModel:
    def __init__(self, model):
        self.model = model
        self.link = None
        self.network = None
        self.left_nodes = []
        self.colors = []
        self.right_nodes = []
        self.available_languages = []
        self.selected_languages = []
        self.timeline_values = []
        self.selected_timeline_value = None
        self.analysis_mode = 0
        self.analysis_options = [
            "Article analysis (no backlinks)",
            "Network analysis (with backlinks)",
        ]
        self.max_metric = None

    async def update_link(self):
        logging.debug("Update link")
        print(self.link)
        await self.model.get_article_data(article_name="Bitwa pod Cedynią")
        self._update_network()
        self.colors = ["#%06x" % random.randint(0, 0xFFFFFF) for node in self.left_nodes]
        self.available_languages = [str(node).split("__")[1] for node in self.left_nodes]
        self.selected_languages = self.available_languages
        metrics = self.model.metrics.sort_values(ascending=False)
        self.max_metric = [metrics.index[0], metrics[0]]
        self.timeline_values = [t.timestamp for t in self.model.timestamps]
        self.selected_timeline_value = self.timeline_values[0]

    def is_existing(self, link):
        return link == "wiki"

    def update_selected_languages(self, selected):
        print("selected languages:", selected)
        self.selected_languages = selected
        self._find_metrics_by_languages()
        # update network

    def update_analysis_mode(self, selected):
        self.analysis_mode = selected
        print(selected)
        # update network

    async def update_timeline_value(self):
        print(self.selected_timeline_value)
        await self.model.get_article_data(
            article_name="Bitwa pod Cedynią",
            moment_in_time=self.timeline_values.index(self.selected_timeline_value)
        )
        self._update_network()
        self._find_metrics_by_languages()

    def _update_network(self):
        self.network = self.model.network
        self.left_nodes, self.right_nodes = (
            [node for node in self.network if "__" in node],
            [node for node in self.network if "__" not in node],
        )

    def _find_metrics_by_languages(self):
        metrics = self.model.metrics
        filtered_by_visible_languages = metrics[
            metrics.index.get_level_values('lang_1').isin(self.selected_languages)
            & metrics.index.get_level_values('lang_2').isin(self.selected_languages)
            ].sort_values(ascending=False)

        self.max_metric = \
            [filtered_by_visible_languages.index[0], filtered_by_visible_languages[0]] \
            if len(filtered_by_visible_languages) > 0 \
            else [("", ""), 0]
