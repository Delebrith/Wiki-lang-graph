from bokeh.document import without_document_lock
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import (
    Plot,
    Range1d,
    HoverTool,
    TapTool,
    BoxSelectTool,
    Circle,
    MultiLine,
    WheelZoomTool,
    NodesAndLinkedEdges,
    Paragraph,
    Slider,
    TextInput,
    CheckboxGroup,
    RadioGroup,
)
from bokeh.palettes import Spectral4
from bokeh.plotting import from_networkx

from scripts.view.Layouts import degree_bipartite_layout


class View:
    def __init__(self, view_model):
        self.view_model = view_model
        self.input_error_message = None
        self.node_renderer_data_source = {}
        self.edge_renderer_data_source = {}
        self.visualization = None

    @without_document_lock
    def modify_doc(self, doc):
        def make_loading_screen():
            loading_text = Paragraph(text="Loading...")
            loading_text.sizing_mode = 'stretch_both'
            screen = loading_text
            doc.add_root(screen)

        def get_network_data():
            G, left_nodes, right_nodes = (
                self.view_model.network,
                self.view_model.left_nodes,
                self.view_model.right_nodes,
            )
            print("got the network")
            return G, left_nodes, right_nodes

        def determine_nodes_visibility(G, left_nodes, right_nodes):
            languages_indices = [self.view_model.available_languages.index(lang) for lang in
                                 self.view_model.selected_languages]
            visible_left_nodes = [left_nodes[i] for i in languages_indices]
            visible_right_nodes = []
            for e in G.edges:
                if e[0] in visible_left_nodes:
                    visible_right_nodes.append(e[1])

            visibility = [
                True
                if (n in visible_right_nodes or n in visible_left_nodes)
                else False
                for n in list(G)
            ]
            return visibility

        def init_visualization_data(G, left_nodes, right_nodes, original_nodes_data):
            self.node_renderer_data_source["index"] = original_nodes_data["index"]
            self.node_renderer_data_source["page"] = original_nodes_data["page"]
            self.node_renderer_data_source["name"] = [p["title"] for p in original_nodes_data["page"]]
            self.node_renderer_data_source["details"] = [p["description"] for p in original_nodes_data["page"]]

            left_colors = self.view_model.colors
            colors = [
                Spectral4[1]
                if n not in left_nodes
                else left_colors[left_nodes.index(n)]
                for n in G
            ]
            self.node_renderer_data_source["color"] = colors

            self.node_renderer_data_source["visibility"] = determine_nodes_visibility(G=G, left_nodes=left_nodes,
                                                                                      right_nodes=right_nodes)

            max_right_degree = max([G.degree(r) for r in right_nodes])
            alpha = [
                0 if self.node_renderer_data_source["visibility"][list(G).index(n)] is False
                else 0.5 if n in left_nodes
                else 0.3 + (0.7 * G.degree(n) / max_right_degree) for n in G
            ]
            self.node_renderer_data_source["alpha"] = alpha

            self.edge_renderer_data_source["start"] = [e[0] for e in G.edges()]
            self.edge_renderer_data_source["end"] = [e[1] for e in G.edges()]
            edges_colors = [colors[list(G).index(e[0])] for e in G.edges()]
            self.edge_renderer_data_source["color"] = edges_colors

            edges_visibility = [self.node_renderer_data_source["visibility"][list(G).index(e[0])] for e in G.edges()]
            edges_alphas = [
                0 if edges_visibility[list(G.edges).index(e)] is False
                else 0.5
                for e in G.edges
            ]
            self.edge_renderer_data_source["alpha"] = edges_alphas

        def prepare_plot(width=1000, height=600, vertical_margin=10):
            plot = Plot(
                plot_width=width,
                plot_height=height,
                x_range=Range1d(-1.1, 1.1),
                y_range=Range1d(-0.5 - vertical_margin, 0.5 + vertical_margin),
            )
            plot.title.text = "Visualization of article versions and internal links"
            plot.sizing_mode = 'stretch_width'
            return plot

        def make_graph():
            print("star drawing")
            G, left_nodes, right_nodes = get_network_data()

            width = 1000
            height = 10 * len(right_nodes)
            vertical_margin = 0.1 * width / height

            plot = prepare_plot(width=width, height=height, vertical_margin=vertical_margin)

            plot.add_tools(HoverTool(tooltips=None), TapTool(), BoxSelectTool())

            layout = degree_bipartite_layout(G, left_nodes, right_nodes)
            graph_renderer = from_networkx(G, layout, scale=1, center=(0, 0))
            init_visualization_data(G=G, left_nodes=left_nodes, right_nodes=right_nodes,
                                    original_nodes_data=graph_renderer.node_renderer.data_source.data)

            graph_renderer.node_renderer.data_source.data = self.node_renderer_data_source

            graph_renderer.node_renderer.glyph = Circle(
                size=12,
                fill_color="color",
                fill_alpha="alpha",
                line_color="color",
                line_width=1,
                line_alpha="alpha",
            )

            graph_renderer.node_renderer.selection_glyph = Circle(
                size=12,
                fill_color="color",
                fill_alpha="alpha",
                line_color="color",
                line_width=5,
                line_alpha="alpha",
            )

            graph_renderer.node_renderer.hover_glyph = Circle(
                size=13,
                fill_color="color",
                fill_alpha="alpha",
                line_color="color",
                line_width=3,
                line_alpha="alpha",
            )

            graph_renderer.edge_renderer.data_source.data = self.edge_renderer_data_source
            graph_renderer.node_renderer.glyph.properties_with_values()
            graph_renderer.edge_renderer.glyph = MultiLine(
                line_color="color", line_alpha="alpha", line_width=2
            )
            graph_renderer.edge_renderer.selection_glyph = MultiLine(
                line_color="color", line_alpha="alpha", line_width=5
            )
            graph_renderer.edge_renderer.hover_glyph = MultiLine(
                line_color="color", line_alpha="alpha", line_width=3
            )

            hover = HoverTool(
                tooltips=[("name", "@name"), ("details", "@details")]
            )
            plot.add_tools(hover, TapTool(), BoxSelectTool(), WheelZoomTool())

            graph_renderer.selection_policy = NodesAndLinkedEdges()
            graph_renderer.inspection_policy = NodesAndLinkedEdges()

            plot.renderers.append(graph_renderer)
            print("rendered")
            return plot

        def make_timeline_slider():
            header = Paragraph(
                text="Select moment in time: %s"
                     % self.view_model.selected_timeline_value
            )

            selected_index = (
                0
                if self.view_model.network is None
                else self.view_model.timeline_values.index(
                    self.view_model.selected_timeline_value
                )
            )
            slider = Slider(
                start=0,
                end=len(self.view_model.timeline_values) - 1,
                value=selected_index,
                show_value=False,
                step=1,
            )

            def update_timeline_value(attr, old, new):
                doc.clear()
                make_loading_screen()
                new_value = self.view_model.timeline_values[new]
                self.view_model.selected_timeline_value = new_value
                curdoc().add_next_tick_callback(self.view_model.update_timeline_value)
                header.text = "Select moment in time: %s" % new_value
                doc.clear()
                self.modify_doc(doc)

            slider.on_change("value", update_timeline_value)
            return column(header, slider)

        def make_text_input():
            text_input = TextInput(
                title="Insert link to wikipedia article",
                value="article title | language" if self.view_model.article is None else self.view_model.article,
            )

            def update_link(attr, old, new):
                doc.clear()
                make_loading_screen()

                async def proceed_update():
                    self.view_model.article = new
                    exists = await self.view_model.check_article_exists()
                    if exists:
                        self.input_error_message = None
                        await self.view_model.update_article()
                    else:
                        self.input_error_message = "Article %s not found." % old
                        self.view_model.article = None
                    doc.clear()
                    self.modify_doc(doc)

                curdoc().add_next_tick_callback(proceed_update)

            text_input.on_change("value", update_link)
            return text_input

        def make_static_header(text):
            return Paragraph(text=text)

        def make_language_checkbox():
            def update_selected(attr, old, new):
                doc.clear()
                make_loading_screen()
                selection = list()
                for i in new:
                    selection.append(self.view_model.available_languages[i])
                self.view_model.update_selected_languages(selection)
                doc.clear()
                self.modify_doc(doc)

            options = self.view_model.available_languages
            checked = self.view_model.selected_languages
            active = [options.index(c) for c in checked]
            checkbox_group = CheckboxGroup(
                name="languages", labels=options, active=active
            )
            checkbox_group.on_change("active", update_selected)
            return checkbox_group

        def make_analysis_mode_radio():
            def update_selected(attr, old, new):
                async def proceed_update():
                    await self.view_model.update_analysis_mode()
                    doc.clear()
                    self.modify_doc(doc)

                doc.clear()
                make_loading_screen()
                self.view_model.analysis_mode = new
                curdoc().add_next_tick_callback(proceed_update)

            active = self.view_model.analysis_options.index(self.view_model.analysis_mode)
            radio_group = RadioGroup(
                name="Analysis mode",
                labels=self.view_model.analysis_options,
                active=active,
            )
            radio_group.on_change("active", update_selected)
            return radio_group

        def make_error_text():
            text_output = Paragraph(
                text=self.input_error_message, style={"color": "red"}
            )
            return text_output

        if self.input_error_message is not None:
            print("there was error")
            column1 = column(
                        make_static_header("Wiki-lang-graph"),
                        make_text_input(),
                        make_error_text(),
                        margin=(10, 10, 10, 10),
                    )
            column2 = column(
                        make_static_header("Most different versions: "),
                        make_static_header("Difference is: "),
                        prepare_plot(),
                        margin=(10, 10, 10, 10),
                    )
            column2.sizing_mode = 'stretch_width'
            doc.add_root(
                row(
                    column1,
                    column2
                )
            )
        elif self.input_error_message is None and self.view_model.network is None:
            print("network was none")
            column1 = column(
                        make_static_header("Wiki-lang-graph"),
                        make_text_input(),
                        margin=(10, 10, 10, 10),
                    )
            column2 = column(
                        make_static_header("Most different versions: "),
                        make_static_header("Difference is: "),
                        prepare_plot(),
                        margin=(10, 10, 10, 10),
                    )
            column2.sizing_mode = 'stretch_width'
            doc.add_root(
                row(
                    column1,
                    column2
                )
            )
        else:
            print("network was there")
            column1 = column(
                        make_static_header("Wiki-lang-graph"),
                        make_text_input(),
                        make_static_header("Select from available languages"),
                        make_language_checkbox(),
                        make_timeline_slider(),
                        make_static_header("What kind of analysis is performed?"),
                        make_analysis_mode_radio(),
                        margin=(10, 10, 10, 10),
                    )
            column2 = column(
                        make_static_header("Most different versions: %s %s" % self.view_model.max_metric[0]),
                        make_static_header("Difference is: %f" % self.view_model.max_metric[1]),
                        make_graph(),
                        margin=(10, 10, 10, 10),
                    )
            column2.sizing_mode = 'stretch_width'
            doc.add_root(
                row(
                    column1,
                    column2,
                )
            )
