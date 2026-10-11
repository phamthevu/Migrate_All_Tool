from __future__ import annotations
import math
import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QLabel, QPushButton,
    QFileDialog, QMessageBox, QInputDialog, QToolTip, QGraphicsItem,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSizePolicy)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QCursor, QFont
from app.core.ranking import pairwise_rank_correlations, directions_from_names


class DraggableLabel(pg.TextItem):
    """A plot label whose location is retained in app state after dragging."""
    def __init__(self, text, anchor, on_release):
        super().__init__(text=text, color="#172033", anchor=anchor)
        self._on_release = on_release
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._on_release:
            self._on_release(self.pos())


class VisualTab(QWidget):
    """Research-ready DEMATEL and final-ranking charts with clean export."""
    def __init__(self, state):
        super().__init__()
        self.state = state
        root = QHBoxLayout(self)
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setMinimumWidth(350)
        self.settings_tabs.setMaximumWidth(390)
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        box = QGroupBox("Figure settings")
        form = QFormLayout(box)
        self.cb_chart = QComboBox()
        self.cb_chart.currentIndexChanged.connect(self.refresh_from_state)
        self.cb_metric = QComboBox()
        self.cb_metric.currentIndexChanged.connect(self.on_metric_changed)
        self._last_metric_name = ""
        self.cb_x = QComboBox(); self.cb_x.addItems(["R+C inc", "R+C dec", "R-C inc", "R-C dec"])
        self.cb_y = QComboBox(); self.cb_y.addItems(["R-C inc", "R-C dec", "R+C inc", "R+C dec"])
        for cb in (self.cb_x, self.cb_y): cb.currentIndexChanged.connect(self.refresh_from_state)
        self.cb_direction = QComboBox(); self.cb_direction.addItems(["Higher is better", "Lower is better"])
        self.cb_direction.currentIndexChanged.connect(self.refresh_from_state)
        self.sp_min = QDoubleSpinBox(); self.sp_min.setRange(-1e9, 1e9); self.sp_min.setDecimals(6); self.sp_min.setSingleStep(.01)
        self.sp_min.valueChanged.connect(self.refresh_from_state)
        self.sp_topk = QSpinBox(); self.sp_topk.setRange(0, 1000); self.sp_topk.setSpecialValueText("All"); self.sp_topk.valueChanged.connect(self.refresh_from_state)
        self.sp_topn = QSpinBox(); self.sp_topn.setRange(0, 9999); self.sp_topn.setSpecialValueText("All"); self.sp_topn.valueChanged.connect(self.refresh_from_state)
        self.sp_nodes = QSpinBox(); self.sp_nodes.setRange(4, 40); self.sp_nodes.setValue(14); self.sp_nodes.valueChanged.connect(self.refresh_from_state)
        self.sp_head = QSpinBox(); self.sp_head.setRange(3, 40); self.sp_head.setValue(11); self.sp_head.valueChanged.connect(self.refresh_from_state)
        self.sp_pad_x = QDoubleSpinBox(); self.sp_pad_x.setRange(.5, 5); self.sp_pad_x.setSingleStep(.1); self.sp_pad_x.setValue(1.0); self.sp_pad_x.valueChanged.connect(self.refresh_from_state)
        self.sp_pad_y = QDoubleSpinBox(); self.sp_pad_y.setRange(.5, 5); self.sp_pad_y.setSingleStep(.1); self.sp_pad_y.setValue(1.2); self.sp_pad_y.valueChanged.connect(self.refresh_from_state)
        self.sp_jitter = QDoubleSpinBox(); self.sp_jitter.setRange(0, .15); self.sp_jitter.setDecimals(3); self.sp_jitter.setSingleStep(.01); self.sp_jitter.setValue(0); self.sp_jitter.valueChanged.connect(self.refresh_from_state)
        self.chk_arrows = QCheckBox("Show arrowheads"); self.chk_arrows.setChecked(True); self.chk_arrows.toggled.connect(self.refresh_from_state)
        self.chk_labels = QCheckBox("Show factor-name labels"); self.chk_labels.setChecked(True); self.chk_labels.toggled.connect(self.refresh_from_state)
        self.chk_grid = QCheckBox("Grid"); self.chk_grid.setChecked(True); self.chk_grid.toggled.connect(self.refresh_from_state)
        self.chk_line_rc0 = QCheckBox("Show R−C = 0 reference"); self.chk_line_rc0.setChecked(True); self.chk_line_rc0.toggled.connect(self.refresh_from_state)
        self.chk_line_prom_mid = QCheckBox("Show mean R+C reference"); self.chk_line_prom_mid.setChecked(True); self.chk_line_prom_mid.toggled.connect(self.refresh_from_state)
        self.cb_shape_cause = QComboBox(); self.cb_shape_cause.addItems(["Circle", "Square", "Triangle"]); self.cb_shape_cause.currentIndexChanged.connect(self.refresh_from_state)
        self.cb_shape_effect = QComboBox(); self.cb_shape_effect.addItems(["Triangle", "Circle", "Square"]); self.cb_shape_effect.currentIndexChanged.connect(self.refresh_from_state)
        self.chk_w_opacity = QCheckBox("Weight controls node opacity"); self.chk_w_opacity.toggled.connect(self.refresh_from_state)
        self.chk_w_size = QCheckBox("Weight controls node size"); self.chk_w_size.setChecked(True); self.chk_w_size.toggled.connect(self.refresh_from_state)
        self.chk_show_weight_labels = QCheckBox("Show weight beside factor label"); self.chk_show_weight_labels.toggled.connect(self.refresh_from_state)
        self.ed_title = QComboBox(); self.ed_title.setEditable(True); self.ed_title.addItem(""); self.ed_title.setCurrentText(""); self.ed_title.currentTextChanged.connect(self.refresh_from_state)
        form.addRow("Chart", self.cb_chart)
        form.addRow("Result column", self.cb_metric)
        form.addRow("X axis (DEMATEL)", self.cb_x)
        form.addRow("Y axis (DEMATEL)", self.cb_y)
        form.addRow("Ranking direction", self.cb_direction)
        form.addRow("Minimum influence", self.sp_min)
        form.addRow("Top-K outgoing links", self.sp_topk)
        form.addRow("Top-N nodes / alternatives", self.sp_topn)
        form.addRow("Node size", self.sp_nodes)
        form.addRow("Arrowhead size", self.sp_head)
        form.addRow("X range padding", self.sp_pad_x)
        form.addRow("Y range padding", self.sp_pad_y)
        form.addRow("Scatter jitter", self.sp_jitter)
        form.addRow("Cause node shape", self.cb_shape_cause)
        form.addRow("Effect node shape", self.cb_shape_effect)
        form.addRow("", self.chk_arrows)
        form.addRow("", self.chk_labels)
        form.addRow("", self.chk_grid)
        form.addRow("", self.chk_line_rc0)
        form.addRow("", self.chk_line_prom_mid)
        form.addRow("", self.chk_w_opacity)
        form.addRow("", self.chk_w_size)
        form.addRow("", self.chk_show_weight_labels)
        form.addRow("Figure title", self.ed_title)
        self.btn_export = QPushButton("Export figure…")
        self.btn_export.clicked.connect(self.export_figure)
        form.addRow("", self.btn_export)
        self.btn_reset_labels = QPushButton("Reset label positions")
        self.btn_reset_labels.clicked.connect(self.reset_label_positions)
        form.addRow("", self.btn_reset_labels)
        self.btn_clear_focus = QPushButton("Clear factor focus")
        self.btn_clear_focus.clicked.connect(self.clear_factor_focus)
        form.addRow("", self.btn_clear_focus)
        # Start with an empty note area. The old generic prompt looked like a
        # plot annotation even before a chart had been loaded.
        self.lbl_note = QLabel("")
        self.lbl_note.setWordWrap(True)
        settings_layout.addWidget(box)
        settings_scroll = QScrollArea(); settings_scroll.setWidgetResizable(True); settings_scroll.setWidget(settings_page)
        self.settings_tabs.addTab(settings_scroll, "Visual options")
        bin_page = QWidget(); bin_layout = QVBoxLayout(bin_page)
        bin_layout.addWidget(QLabel("Configure each influence interval: bounds, opacity (0–20), and dash style (0–20)."))
        self.tbl_seg = QTableWidget(0, 4)
        self.tbl_seg.setHorizontalHeaderLabels(["Lower", "Upper", "Opacity", "Dash"])
        self.tbl_seg.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_seg.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_seg.itemChanged.connect(self._on_bin_table_changed)
        bin_layout.addWidget(self.tbl_seg)
        self.lbl_edge_minmax = QLabel("Influence range: —"); bin_layout.addWidget(self.lbl_edge_minmax)
        self.settings_tabs.addTab(bin_page, "Arrow intervals")
        root.addWidget(self.settings_tabs)

        self.plot = pg.PlotWidget(background="w")
        self.plot.setMinimumWidth(620)
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Keep chart content changes (for example, long factor names on the
        # Y axis) from changing the available plot width from one redraw to
        # the next.
        self.plot.getAxis("left").setWidth(160)
        self.plot.getAxis("bottom").setHeight(48)
        self.plot.showGrid(x=True, y=True, alpha=.2)
        self.plot.setMenuEnabled(True)
        root.addWidget(self.plot, 1)
        self._selected_idx = None
        self._hover_nodes = []
        self._hover_edges = []
        self._legend = None
        self._bin_edges = []
        self._bin_intervals = []
        self._bin_styles = []
        self._chart_options = []
        self._metric_options = []
        self._last_view_key = None
        self.plot.scene().sigMouseMoved.connect(self._on_plot_mouse_moved)
        self.refresh_from_state()

    def _sync_options(self):
        d = self.state.data
        current = self.cb_chart.currentText()
        if d.method == "DEMATEL":
            charts = ["INRM influence network", "Prominence–relation quadrants", "Influence heatmap", "Prominence ranking"]
            self.cb_metric.setEnabled(False); self.cb_direction.setEnabled(False)
        else:
            charts = ["Score bar chart", "Score lollipop", "Ranked dot plot", "Multi-metric profile",
                      "Rank comparison", "Spearman rank correlation", "Kendall rank correlation"]
        if charts != self._chart_options:
            self.cb_chart.blockSignals(True)
            self.cb_chart.clear(); self.cb_chart.addItems(charts)
            if current in charts: self.cb_chart.setCurrentText(current)
            self.cb_chart.blockSignals(False)
            self._chart_options = list(charts)
        uses_metric = d.method == "Ranking" and self.cb_chart.currentText() in charts[:4]
        self.cb_metric.setEnabled(uses_metric); self.cb_direction.setEnabled(uses_metric)
        cols = d.ranking_columns if d.method == "Ranking" else []
        selected = self.cb_metric.currentText()
        if cols != self._metric_options:
            self.cb_metric.blockSignals(True); self.cb_metric.clear(); self.cb_metric.addItems(cols)
            if selected in cols: self.cb_metric.setCurrentText(selected)
            self.cb_metric.blockSignals(False)
            self._metric_options = list(cols)
        metric_name = self.cb_metric.currentText()
        if metric_name and metric_name != self._last_metric_name:
            self._last_metric_name = metric_name
            lower_is_better = any(token in metric_name.lower() for token in ("rank", "distance", "cost", "error", "loss"))
            self.cb_direction.blockSignals(True)
            self.cb_direction.setCurrentIndex(1 if lower_is_better else 0)
            self.cb_direction.blockSignals(False)
        network = d.method == "DEMATEL" and self.cb_chart.currentText() == "INRM influence network"
        for w in (self.cb_x, self.cb_y, self.sp_min, self.sp_topk, self.sp_nodes, self.sp_head,
                  self.sp_pad_x, self.sp_pad_y, self.sp_jitter, self.chk_arrows,
                  self.cb_shape_cause, self.cb_shape_effect, self.chk_w_opacity,
                  self.chk_w_size, self.chk_show_weight_labels):
            w.setEnabled(network)
        self.chk_line_rc0.setEnabled(d.method == "DEMATEL" and self.cb_chart.currentText() in ("INRM influence network", "Prominence–relation quadrants"))
        self.chk_line_prom_mid.setEnabled(d.method == "DEMATEL" and self.cb_chart.currentText() in ("INRM influence network", "Prominence–relation quadrants"))
        self.tbl_seg.setEnabled(network)
        self.settings_tabs.setTabEnabled(1, network)
        self.sp_topn.setEnabled(True)
        self.btn_reset_labels.setEnabled(d.method == "DEMATEL")
        self.btn_clear_focus.setEnabled(network)

    def on_metric_changed(self, *args):
        name = self.cb_metric.currentText().lower()
        lower_is_better = any(token in name for token in ("rank", "distance", "cost", "error", "loss"))
        self._last_metric_name = self.cb_metric.currentText()
        self.cb_direction.blockSignals(True)
        self.cb_direction.setCurrentIndex(1 if lower_is_better else 0)
        self.cb_direction.blockSignals(False)
        self.refresh_from_state()

    def refresh_from_state(self, *args):
        self._sync_options()
        d = self.state.data
        chart_key = (d.method, self.cb_chart.currentText(), id(d.matrix), id(d.ranking_values), tuple(d.labels), tuple(d.ranking_labels))
        preserve_view = (
            chart_key == self._last_view_key
            and not (d.method == "DEMATEL" and self.cb_chart.currentText() in
                     ("INRM influence network", "Prominence–relation quadrants"))
        )
        saved_view = self.plot.getViewBox().viewRange() if preserve_view else None
        # PlotWidget.clear() does not reliably clear LegendItem's internal
        # reference. Detach it explicitly so redraws cannot stack legends.
        plot_item = self.plot.getPlotItem()
        old_legend = self._legend or getattr(plot_item, "legend", None)
        if old_legend is not None:
            try:
                scene = old_legend.scene()
                if scene is not None: scene.removeItem(old_legend)
            except Exception: pass
            try: plot_item.legend = None
            except Exception: pass
        self._legend = None
        self.plot.clear()
        self._hover_nodes = []
        self._hover_edges = []
        self._placed_label_rects = []
        self._label_node_centers = []
        self.plot.getViewBox().invertY(False)
        self.plot.getAxis("bottom").setTicks(None)
        self.plot.getAxis("left").setTicks(None)
        self.plot.setLabel("bottom", "")
        self.plot.setLabel("left", "")
        self.plot.setBackground("w")
        self.plot.showGrid(x=self.chk_grid.isChecked(), y=self.chk_grid.isChecked(), alpha=.2)
        if d.method == "DEMATEL" and d.dematel_table:
            chart = self.cb_chart.currentText()
            if chart == "INRM influence network": self._draw_inrm()
            elif chart == "Prominence–relation quadrants": self._draw_quadrants()
            elif chart == "Influence heatmap": self._draw_heatmap()
            else: self._draw_prominence()
        elif d.method == "Ranking" and d.ranking_values is not None and d.ranking_labels:
            chart = self.cb_chart.currentText()
            if chart == "Multi-metric profile": self._draw_profile()
            elif chart == "Rank comparison": self._draw_rank_comparison()
            elif chart == "Spearman rank correlation": self._draw_rank_correlation("spearman")
            elif chart == "Kendall rank correlation": self._draw_rank_correlation("kendall")
            else: self._draw_ranking(chart)
        if saved_view is not None:
            self.plot.setXRange(*saved_view[0], padding=0)
            self.plot.setYRange(*saved_view[1], padding=0)
        elif not (d.method == "DEMATEL" and self.cb_chart.currentText() in ("INRM influence network", "Prominence–relation quadrants")):
            self.plot.autoRange(padding=.08)
        title = self.ed_title.currentText().strip()
        self.plot.setTitle(title, color="#172033", size="12pt")
        self._last_view_key = chart_key

    def clear_factor_focus(self):
        self._selected_idx = None
        self.refresh_from_state()

    def reset_label_positions(self):
        self.state.data.label_positions.clear()
        self.refresh_from_state()

    def _on_node_clicked(self, _scatter, points, _event):
        if not points: return
        idx = points[0].data()
        if idx is None: return
        idx = int(idx)
        self._selected_idx = None if self._selected_idx == idx else idx
        self.refresh_from_state()

    @staticmethod
    def _segment_distance(point, start, end):
        px, py = point.x(), point.y()
        ax, ay = start.x(), start.y(); bx, by = end.x(), end.y()
        dx, dy = bx-ax, by-ay
        den = dx*dx + dy*dy
        t = 0.0 if den == 0 else max(0.0, min(1.0, ((px-ax)*dx+(py-ay)*dy)/den))
        return math.hypot(px-(ax+t*dx), py-(ay+t*dy))

    def _on_plot_mouse_moved(self, pos):
        if not self.plot.getViewBox().sceneBoundingRect().contains(pos):
            QToolTip.hideText(); return
        d = self.state.data
        best_node = None; best_distance = 1e9
        vb = self.plot.getViewBox()
        for row in self._hover_nodes:
            scene_pos = vb.mapViewToScene(pg.Point(row["x"], row["y"]))
            distance = math.hypot(pos.x()-scene_pos.x(), pos.y()-scene_pos.y())
            if distance < best_distance:
                best_node, best_distance = row, distance
        if best_node is not None and best_distance <= best_node["radius"] + 7:
            i = best_node["index"]
            r = d.dematel_table[i]
            tip = (f"<b>{d.labels[i]}</b><br>R: {r['R']:.6g}<br>C: {r['C']:.6g}"
                   f"<br>R+C: {r['R+C']:.6g}<br>R−C: {r['R-C']:.6g}"
                   f"<br>Weight: {r['Weight']:.6g}<br>Rank: {r['Rank']}<br>Group: {r['Group']}"
                   "<br><i>Click node to focus its incoming/outgoing links</i>")
            QToolTip.showText(QCursor.pos(), tip, self.plot)
            return
        closest = None; edge_distance = 1e9
        for edge in self._hover_edges:
            points = [vb.mapViewToScene(point) for point in edge["view_points"]]
            for a, b in zip(points[:-1], points[1:]):
                dist = self._segment_distance(pos, a, b)
                if dist < edge_distance:
                    closest, edge_distance = edge, dist
        if closest is not None and edge_distance <= 7:
            tip = (f"<b>{d.labels[closest['i']]} → {d.labels[closest['j']]}</b>"
                   f"<br>Tᵢⱼ: {closest['value']:.7g}")
            QToolTip.showText(QCursor.pos(), tip, self.plot)
        else:
            QToolTip.hideText()

    def _dematel_arrays(self):
        d = self.state.data
        table = d.dematel_table
        p = np.array([r["R+C"] for r in table], float)
        r = np.array([r["R-C"] for r in table], float)
        w = np.array([r["Weight"] for r in table], float)
        return p, r, w

    def _axis_values(self):
        p, r, _ = self._dematel_arrays()
        def values(choice):
            base = p if "R+C" in choice else r
            return -base if choice.endswith("dec") else base
        return values(self.cb_x.currentText()), values(self.cb_y.currentText())

    def _draw_inrm(self):
        d = self.state.data
        mat = np.asarray(d.matrix, float)
        x, y = self._axis_values()
        p, rel, weights = self._dematel_arrays()
        n = len(d.labels)
        topn = self.sp_topn.value()
        keep = np.arange(n) if topn <= 0 or topn >= n else np.argsort(-weights, kind="stable")[:topn]
        if self.sp_jitter.value() > 0:
            rng = np.random.default_rng(481)
            x = x + rng.uniform(-self.sp_jitter.value(), self.sp_jitter.value(), size=n)
            y = y + rng.uniform(-self.sp_jitter.value(), self.sp_jitter.value(), size=n)
        threshold = self.sp_min.value()
        links = []
        for i in keep:
            for j in keep:
                if i == j: continue
                value = mat[i, j]
                if value > 0 and value >= threshold: links.append((float(value), int(i), int(j)))
        links.sort(key=lambda e: -e[0])
        if self.sp_topk.value() > 0:
            per_src = {}
            for val, i, j in links: per_src.setdefault(i, []).append((val, i, j))
            links = [e for row in per_src.values() for e in row[:self.sp_topk.value()]]
        self._ensure_bin_table([e[0] for e in links] or mat[mat > 0])
        node_colors = [(220, 70, 60, 225) if rel[i] > 1e-12 else (55, 105, 190, 225) if rel[i] < -1e-12 else (120, 120, 120, 225) for i in range(n)]
        scale = weights[keep]; denom = max(float(np.ptp(scale)), 1e-12)
        sizes = {int(i): (11 + 13 * (weights[i] - scale.min()) / denom if self.chk_w_size.isChecked() else float(self.sp_nodes.value())) for i in keep}
        xr, yr = self._padded_range(x[keep], self.sp_pad_x.value()), self._padded_range(y[keep], self.sp_pad_y.value())
        self.plot.setXRange(*xr, padding=0); self.plot.setYRange(*yr, padding=0)
        vb=self.plot.getViewBox()
        self._label_node_centers=[(d.labels[int(i)],vb.mapViewToScene(pg.Point(float(x[i]),float(y[i]))),float(sizes[int(i)])) for i in keep]
        # Draw arrows in screen coordinates so their tips are consistently clipped to node borders.
        edge_max = max((e[0] for e in links), default=1.0)
        for val, i, j in links:
            self._draw_link(x, y, i, j, val, float(sizes.get(j, 12)),
                            float(sizes.get(i, 12)), edge_max,
                            curved=bool(mat[j, i] > 0))
        spots=[]
        for i in keep:
            group = d.dematel_table[i]["Group"]
            selected = self._selected_idx == int(i)
            symbol = self._shape_symbol(self.cb_shape_cause.currentText()) if group == "Cause" else self._shape_symbol(self.cb_shape_effect.currentText()) if group == "Effect" else "s"
            brush = node_colors[i]
            if self.chk_w_opacity.isChecked():
                alpha = int(65 + 180 * (weights[i] - scale.min()) / denom)
                brush = (*brush[:3], alpha)
            spots.append({"pos": (x[i], y[i]), "size": sizes[int(i)], "data": int(i),
                          "symbol": symbol, "brush": brush,
                          "pen": pg.mkPen("#f59e0b" if selected else "#263445", width=2.6 if selected else 0.8)})
        sc = pg.ScatterPlotItem(spots=spots); self.plot.addItem(sc)
        sc.sigClicked.connect(self._on_node_clicked)
        self._hover_nodes = [{"index": int(i), "x": float(x[i]), "y": float(y[i]),
                              "radius": float(sizes[int(i)]/2)} for i in keep]
        if self.chk_labels.isChecked():
            for order, i in enumerate(keep):
                label = d.labels[i] + (f"  W={weights[i]:.3g}" if self.chk_show_weight_labels.isChecked() else "")
                self._add_node_label(label, x[i], y[i], order, key=d.labels[i])
        self._add_reference_lines(x[keep], y[keep], self.cb_x.currentText(), self.cb_y.currentText())
        self.plot.setLabel("left", self._axis_label(self.cb_y.currentText()))
        self.plot.setLabel("bottom", self._axis_label(self.cb_x.currentText()))
        if self._selected_idx is not None and self._selected_idx < len(d.labels):
            self.lbl_note.setText(f"Focused: {d.labels[self._selected_idx]} · orange arrows go out; blue arrows point in. Click the node or Clear factor focus to reset.")
        else:
            self.lbl_note.setText(f"{len(keep)} nodes · {len(links)} links. Reciprocal links curve apart. Click a node to focus its in/out links.")
        self._add_network_legend(edge_max)

    @staticmethod
    def _nice_range(arr):
        lo, hi = float(np.min(arr)), float(np.max(arr))
        span = hi-lo
        if span == 0: span = max(abs(lo)*.15, 1.0)
        return lo-.10*span, hi+.10*span

    @staticmethod
    def _padded_range(arr, factor):
        lo, hi = float(np.min(arr)), float(np.max(arr))
        span = hi - lo
        if span <= 1e-12: span = max(abs(lo) * .15, 1.0)
        half = .5 * span / max(float(factor), .1)
        center = (lo + hi) / 2
        return center - half, center + half

    @staticmethod
    def _axis_label(choice):
        base = "R+C (prominence)" if "R+C" in choice else "R−C (net cause / effect)"
        return base + (" · reversed" if choice.endswith("dec") else "")

    @staticmethod
    def _shape_symbol(shape):
        return {"Circle": "o", "Square": "s", "Triangle": "t"}.get(shape, "o")

    def _add_reference_lines(self, x, y, x_choice, y_choice):
        p, rel, _ = self._dematel_arrays()
        dashed = pg.mkPen("#64748b", width=1.2, style=Qt.PenStyle.DashLine)
        if self.chk_line_rc0.isChecked():
            if "R-C" in x_choice:
                self.plot.addItem(pg.InfiniteLine(pos=0, angle=90, pen=dashed))
            if "R-C" in y_choice:
                self.plot.addItem(pg.InfiniteLine(pos=0, angle=0, pen=dashed))
        if self.chk_line_prom_mid.isChecked():
            shown = x if "R+C" in x_choice else y if "R+C" in y_choice else None
            if shown is None: return
            mid = float((np.min(shown) + np.max(shown)) / 2.0)
            if "R+C" in x_choice:
                self.plot.addItem(pg.InfiniteLine(pos=mid, angle=90, pen=pg.mkPen("#0f766e", width=1.5, style=Qt.PenStyle.DashLine)))
            if "R+C" in y_choice:
                self.plot.addItem(pg.InfiniteLine(pos=mid, angle=0, pen=pg.mkPen("#0f766e", width=1.5, style=Qt.PenStyle.DashLine)))

    def _ensure_bin_table(self, values):
        vals = np.asarray(values, float); vals = vals[np.isfinite(vals)]
        if not vals.size: vals = np.array([0.0, 1.0])
        lo, hi = float(vals.min()), float(vals.max())
        if hi <= lo: hi = lo + max(abs(lo) * .01, 1e-9)
        count = max(2, min(20, int(self.state.data.vis.bins)))
        edges = np.linspace(lo, hi, count + 1).tolist()
        signature = (count, round(lo, 12), round(hi, 12), id(self.state.data.matrix))
        if getattr(self, "_bin_signature", None) != signature:
            self._bin_signature = signature
            self._bin_edges = edges
            self._bin_intervals = list(zip(edges[:-1], edges[1:]))
            self._bin_styles = [{"opacity": 2 if row < count-1 else 6, "dash": 0} for row in range(count)]
            self.tbl_seg.blockSignals(True); self.tbl_seg.setRowCount(count)
            for row in range(count):
                for col, value in enumerate((edges[row], edges[row+1], self._bin_styles[row]["opacity"], 0)):
                    item = QTableWidgetItem(f"{value:.6g}" if col < 2 else str(value))
                    self.tbl_seg.setItem(row, col, item)
            self.tbl_seg.blockSignals(False)
        else:
            self._bin_intervals = self._read_table_intervals()
            self._bin_edges = [self._bin_intervals[0][0]] + [pair[1] for pair in self._bin_intervals]
            self._bin_styles = self._read_table_styles()
        self.lbl_edge_minmax.setText(f"Influence range: {lo:.6g} – {hi:.6g} · {count} intervals")

    def _read_table_intervals(self):
        try:
            intervals=[]
            for row in range(self.tbl_seg.rowCount()):
                low=float(self.tbl_seg.item(row,0).text()); high=float(self.tbl_seg.item(row,1).text())
                if high <= low: raise ValueError("upper bound must exceed lower bound")
                intervals.append((low,high))
            return intervals
        except (AttributeError, ValueError):
            return list(self._bin_intervals)

    def _bin_index(self, value):
        for idx, (low, high) in enumerate(self._bin_intervals):
            if low <= value <= high:
                return idx
        if not self._bin_intervals: return 0
        return min(range(len(self._bin_intervals)), key=lambda idx: min(abs(value-self._bin_intervals[idx][0]), abs(value-self._bin_intervals[idx][1])))

    def _read_table_styles(self):
        styles=[]
        for row in range(self.tbl_seg.rowCount()):
            try: op=int(float(self.tbl_seg.item(row,2).text()))
            except (AttributeError,ValueError): op=14
            try: dash=int(float(self.tbl_seg.item(row,3).text()))
            except (AttributeError,ValueError): dash=0
            styles.append({"opacity": max(0,min(20,op)), "dash": max(0,min(20,dash))})
        return styles

    def _on_bin_table_changed(self, item):
        if item.column() >= 2:
            try: value=max(0,min(20,int(float(item.text()))))
            except ValueError: value=14 if item.column()==2 else 0
            self.tbl_seg.blockSignals(True); item.setText(str(value)); self.tbl_seg.blockSignals(False)
        intervals=self._read_table_intervals()
        if len(intervals) == self.tbl_seg.rowCount(): self._bin_intervals=intervals
        self._bin_styles=self._read_table_styles()
        self.refresh_from_state()

    def _draw_link(self, x, y, i, j, value, target_radius, source_radius, edge_max, curved=False):
        bin_id = self._bin_index(value)
        style = self._bin_styles[bin_id]
        if style["opacity"] <= 0: return
        vb=self.plot.getViewBox()
        p1=vb.mapViewToScene(pg.Point(float(x[i]),float(y[i])))
        p2=vb.mapViewToScene(pg.Point(float(x[j]),float(y[j])))
        dx,dy=p2.x()-p1.x(),p2.y()-p1.y(); length=math.hypot(dx,dy)
        if length < 1: return
        ux,uy=dx/length,dy/length
        tip=p2-pg.Point(ux*(target_radius+2),uy*(target_radius+2))
        start=p1+pg.Point(ux*(source_radius*.48),uy*(source_radius*.48))
        normal_x,normal_y=-uy,ux
        control=pg.Point((start.x()+tip.x())/2,(start.y()+tip.y())/2)
        if curved:
            control=control+pg.Point(normal_x*20,normal_y*20)
        scene_points=[]
        for step in range(25):
            t=step/24
            omt=1-t
            scene_points.append(pg.Point(omt*omt*start.x()+2*omt*t*control.x()+t*t*tip.x(),
                                         omt*omt*start.y()+2*omt*t*control.y()+t*t*tip.y()))
        view_points=[vb.mapSceneToView(point) for point in scene_points]
        strength = min(1.0, max(0.0, value / max(edge_max, 1e-12)))
        alpha=int(round(12 + (style["opacity"] / 20.0) * 228))
        width=1.0 + (style["opacity"] / 20.0) * 1.4
        rgb = self._edge_rgb(value)
        if self._selected_idx is not None:
            if i == self._selected_idx: rgb=(225,92,40)
            elif j == self._selected_idx: rgb=(20,125,190)
            else: alpha=max(14,alpha//4); width=max(.55,width*.7)
        dash_value=style["dash"]
        dash_style = Qt.PenStyle.SolidLine if dash_value <= 0 else Qt.PenStyle.DashLine if dash_value <= 7 else Qt.PenStyle.DotLine if dash_value <= 14 else Qt.PenStyle.DashDotLine
        pen=pg.mkPen(color=(*rgb, alpha),width=width,style=dash_style)
        self.plot.plot([point.x() for point in view_points],[point.y() for point in view_points],pen=pen)
        self._hover_edges.append({"i":i,"j":j,"value":value,"view_points":view_points})
        if self.chk_arrows.isChecked():
            px=self.sp_head.value(); half=px*.44
            tx,ty=tip.x()-control.x(),tip.y()-control.y()
            tl=max(math.hypot(tx,ty),1e-9); tx,ty=tx/tl,ty/tl
            base=tip-pg.Point(tx*px,ty*px)
            left=base+pg.Point(-ty*half,tx*half); right=base-pg.Point(-ty*half,tx*half)
            pts=[vb.mapSceneToView(q) for q in (tip,left,right)]
            hp=pen
            self.plot.plot([pts[0].x(),pts[1].x()],[pts[0].y(),pts[1].y()],pen=hp)
            self.plot.plot([pts[0].x(),pts[2].x()],[pts[0].y(),pts[2].y()],pen=hp)

    def _draw_quadrants(self):
        p, rel, weights=self._dematel_arrays(); d=self.state.data
        topn=self.sp_topn.value(); keep=np.arange(len(p)) if topn<=0 or topn>=len(p) else np.argsort(-weights)[:topn]
        self.plot.setXRange(*self._nice_range(p[keep]),padding=.12)
        self.plot.setYRange(*self._nice_range(rel[keep]),padding=.12)
        vb=self.plot.getViewBox()
        self._label_node_centers=[(d.labels[int(i)],vb.mapViewToScene(pg.Point(float(p[i]),float(rel[i]))),12.0) for i in keep]
        colors=[(220,70,60,230) if rel[i]>1e-12 else (55,105,190,230) if rel[i]<-1e-12 else (120,120,120,230) for i in keep]
        sizes=9+np.divide(weights[keep]-weights[keep].min(),max(float(np.ptp(weights[keep])),1e-12))*10
        self.plot.addItem(pg.ScatterPlotItem(x=p[keep],y=rel[keep],size=sizes,brush=colors,pen=pg.mkPen("#263445",width=.7)))
        self.plot.addItem(pg.InfiniteLine(pos=0,angle=0,pen=pg.mkPen("#4b5563",width=1)))
        if self.chk_line_prom_mid.isChecked():
            mid=float((np.min(p[keep])+np.max(p[keep]))/2); self.plot.addItem(pg.InfiniteLine(pos=mid,angle=90,pen=pg.mkPen("#0f766e",width=1.5,style=Qt.PenStyle.DashLine)))
        if self.chk_line_rc0.isChecked(): self.plot.addItem(pg.InfiniteLine(pos=0,angle=0,pen=pg.mkPen("#64748b",style=Qt.PenStyle.DashLine)))
        if self.chk_labels.isChecked():
            for order, i in enumerate(keep): self._add_node_label(d.labels[i], p[i], rel[i], order)
        self.plot.setLabel("bottom","R+C (prominence)"); self.plot.setLabel("left","R−C (net cause / effect)")
        self.lbl_note.setText("Dashed vertical line: median prominence. Point size reflects normalized prominence weight.")

    def _add_node_label(self, text, x, y, order, key=None):
        # Greedy spiral placement keeps dense labels apart; user-dragged
        # positions are retained by factor name across redraws.
        positions=self.state.data.label_positions
        label_key = str(key if key is not None else text)
        label=DraggableLabel(str(text),(.5,.5),
            lambda pos, k=label_key: positions.__setitem__(k,(float(pos.x()),float(pos.y()))))
        label.setFont(QFont("Arial",8))
        label.fill=pg.mkBrush(255,255,255,225); label.border=pg.mkPen(255,255,255,140)
        self.plot.addItem(label)
        vb=self.plot.getViewBox()
        if label_key in positions:
            label.setPos(*positions[label_key])
        else:
            node=vb.mapViewToScene(pg.Point(float(x),float(y)))
            node_rects=[QRectF(center.x()-sz/2-2,center.y()-sz/2-2,sz+4,sz+4)
                        for _,center,sz in self._label_node_centers]
            candidates=[]
            for ring in (20,30,42,56,72,92):
                for step in range(16):
                    angle=(step/16)*2*math.pi
                    dx=math.cos(angle)*ring; dy=math.sin(angle)*ring
                    anchor=(0 if dx>4 else 1 if dx < -4 else .5,
                            1 if dy < -4 else 0 if dy>4 else .5)
                    candidates.append((dx,dy,anchor))
            chosen=None
            for dx,dy,anchor in candidates:
                q=vb.mapSceneToView(node+pg.Point(dx,dy))
                label.setAnchor(anchor); label.setPos(float(q.x()),float(q.y()))
                rect=label.sceneBoundingRect().adjusted(-3,-2,3,2)
                intersects=any(rect.intersects(other) for other in self._placed_label_rects)
                intersects=intersects or any(rect.intersects(other) for other in node_rects)
                if not intersects:
                    chosen=rect; break
            if chosen is None: chosen=label.sceneBoundingRect()
            self._placed_label_rects.append(chosen)
        if label_key in positions:
            self._placed_label_rects.append(label.sceneBoundingRect().adjusted(-3,-2,3,2))

    def _add_network_legend(self, edge_max):
        self._legend=self.plot.addLegend(offset=(10,10))
        self._legend.setBrush(pg.mkBrush(255, 255, 255, 245))
        self._legend.setPen(pg.mkPen(190, 198, 208, 220, width=1))
        cause=pg.ScatterPlotItem([],[],symbol="o",size=9,brush=(220,70,60),pen=pg.mkPen("#263445"))
        effect=pg.ScatterPlotItem([],[],symbol="t",size=9,brush=(55,105,190),pen=pg.mkPen("#263445"))
        neutral=pg.ScatterPlotItem([],[],symbol="s",size=8,brush=(120,120,120),pen=pg.mkPen("#263445"))
        self._legend.addItem(cause,"Cause factor"); self._legend.addItem(effect,"Effect factor")
        self._legend.addItem(neutral,"Neutral factor")
        if self._bin_intervals:
            sample_indices=sorted(set((0, len(self._bin_intervals)//2, len(self._bin_intervals)-1)))
            for idx in sample_indices:
                low,high=self._bin_intervals[idx]; style=self._bin_styles[idx]
                value=(low+high)/2; rgb=self._edge_rgb(value)
                alpha=int(round(12+(style["opacity"]/20)*228)); width=1+(style["opacity"]/20)*1.4
                dash=style["dash"]
                dash_style=Qt.PenStyle.SolidLine if dash<=0 else Qt.PenStyle.DashLine if dash<=7 else Qt.PenStyle.DotLine if dash<=14 else Qt.PenStyle.DashDotLine
                sample=pg.PlotDataItem([],[],pen=pg.mkPen(color=(*rgb,alpha),width=width,style=dash_style))
                self._legend.addItem(sample,f"T={low:.3g}–{high:.3g} · Op {style['opacity']}/20")

    def _edge_rgb(self, value):
        n_bins=max(1,len(self._bin_intervals))
        bin_id=self._bin_index(value)
        mix=bin_id/max(1,n_bins-1)
        return (int(175-120*mix),int(190-120*mix),int(205-105*mix))

    def _draw_heatmap(self):
        d=self.state.data; a=np.asarray(d.matrix,float)
        image=pg.ImageItem(a); self.plot.addItem(image)
        lut=pg.colormap.get("viridis").getLookupTable(0.0,1.0,256); image.setLookupTable(lut)
        lo,hi=float(a.min()),float(a.max()); image.setLevels([lo,hi if hi>lo else lo+1])
        image.setRect(QRectF(0,0,a.shape[0],a.shape[1]))
        ticks=[[(i+.5,str(d.labels[i])) for i in range(len(d.labels))]]
        self.plot.getAxis("bottom").setTicks(ticks); self.plot.getAxis("left").setTicks(ticks)
        self.plot.setLabel("bottom","Source factor"); self.plot.setLabel("left","Target factor")
        self.lbl_note.setText("Cell (i, j) is total influence from factor i to factor j.")

    def _draw_prominence(self):
        p, rel, weights=self._dematel_arrays(); d=self.state.data
        order=np.argsort(p); topn=self.sp_topn.value()
        if topn>0: order=order[-topn:]
        y=np.arange(len(order)); bars=pg.BarGraphItem(x0=np.zeros(len(order)),x1=p[order],y=y,height=.7,brush=(57,111,169,220),pen=pg.mkPen(None))
        self.plot.addItem(bars); self.plot.getAxis("left").setTicks([[(int(i),d.labels[idx]) for i,idx in enumerate(order)]])
        self.plot.setLabel("bottom","Prominence R+C"); self.plot.setLabel("left","Factor")
        self.lbl_note.setText("Factors are ordered by prominence; horizontal bar length equals R+C.")

    def _ranking_data(self):
        d=self.state.data
        if d.ranking_values is None or not d.ranking_columns: return None,None
        c=max(0,self.cb_metric.currentIndex()); c=min(c,d.ranking_values.shape[1]-1)
        values=np.asarray(d.ranking_values[:,c],float)
        higher=self.cb_direction.currentIndex()==0
        order=np.argsort(-values if higher else values,kind="stable")
        topn=self.sp_topn.value()
        if topn>0: order=order[:topn]
        return values,order

    def _draw_ranking(self,chart):
        d=self.state.data; values,order=self._ranking_data()
        if values is None:return
        names=np.array(d.ranking_labels,dtype=object); selected=values[order]; labels=names[order]
        if chart == "Score bar chart":
            y=np.arange(len(order)); self.plot.addItem(pg.BarGraphItem(x0=np.zeros(len(order)),x1=selected,y=y,height=.66,brush=(49,118,168,220),pen=pg.mkPen(None)))
            self.plot.getAxis("left").setTicks([[(int(i),str(v)) for i,v in enumerate(labels)]])
            self.plot.setLabel("bottom",self.cb_metric.currentText()); self.plot.setLabel("left","Alternative")
        elif chart == "Score lollipop":
            y=np.arange(len(order));
            for yi,val in zip(y,selected): self.plot.plot([0,val],[yi,yi],pen=pg.mkPen("#9aa8b5",width=1.5))
            self.plot.addItem(pg.ScatterPlotItem(x=selected,y=y,size=10,brush=(37,115,164,230),pen=pg.mkPen("w",width=1)))
            self.plot.getAxis("left").setTicks([[(int(i),str(v)) for i,v in enumerate(labels)]])
            self.plot.setLabel("bottom",self.cb_metric.currentText()); self.plot.setLabel("left","Alternative")
        else:
            ranks=np.empty(len(values),int); ranks[np.argsort(-values if self.cb_direction.currentIndex()==0 else values,kind="stable")]=np.arange(1,len(values)+1)
            self.plot.addItem(pg.ScatterPlotItem(x=ranks[order],y=selected,size=10,brush=(37,115,164,230),pen=pg.mkPen("w",width=1)))
            if self.chk_labels.isChecked():
                for i in order:
                    t=pg.TextItem(str(names[i]),color="#172033",anchor=(.5,1.2));t.setPos(float(ranks[i]),float(values[i]));self.plot.addItem(t)
            self.plot.setLabel("bottom","Rank (1 = best)");self.plot.setLabel("left",self.cb_metric.currentText())
        self.lbl_note.setText(f"{len(order)} alternatives shown · rank direction: {'higher' if self.cb_direction.currentIndex()==0 else 'lower'} values are better.")

    def _draw_profile(self):
        d=self.state.data; values=np.asarray(d.ranking_values,float)
        if values.shape[1]<2: self.lbl_note.setText("Import at least two result columns for a profile chart."); return
        inds=np.arange(values.shape[1])
        directions=directions_from_names(d.ranking_columns)
        for i,name in enumerate(d.ranking_labels):
            vals=values[i].astype(float); span=np.ptp(values,axis=0); low=np.min(values,axis=0)
            norm=np.divide(vals-low,span,out=np.full_like(vals,.5),where=span>1e-12)
            norm=np.where(directions, norm, 1-norm)
            if len(d.ranking_labels)>12 and i>=12:break
            self.plot.plot(inds,norm,pen=pg.mkPen(pg.intColor(i,hues=max(12,min(24,len(d.ranking_labels)))),width=1.4),symbol="o",symbolSize=5,name=name)
        self.plot.getAxis("bottom").setTicks([[(int(i),c) for i,c in enumerate(d.ranking_columns)]])
        self.plot.setLabel("left","Within-metric normalized value");self.plot.setLabel("bottom","Final result metric")
        self.lbl_note.setText("Each metric is scaled to 0–1 for visual comparison only; this does not alter imported values.")

    def _draw_rank_comparison(self):
        d=self.state.data; vals=np.asarray(d.ranking_values,float)
        if vals.shape[1]<2:self.lbl_note.setText("Import at least two result columns to compare ranks.");return
        result=pairwise_rank_correlations(vals,d.ranking_columns)
        ranks=result["ranks"]
        m=min(vals.shape[1],8)
        for i,name in enumerate(d.ranking_labels):
            if len(d.ranking_labels)>30 and i>=30: break
            self.plot.plot(np.arange(m),ranks[i,:m],pen=pg.mkPen(pg.intColor(i,hues=max(12,min(30,len(d.ranking_labels)))),width=1.4),symbol="o",symbolSize=5,name=name)
        self.plot.getAxis("bottom").setTicks([[(int(i),d.ranking_columns[i]) for i in range(m)]])
        self.plot.invertY(True); self.plot.setLabel("left","Rank (1 = best)");self.plot.setLabel("bottom","Method / result column")
        self.lbl_note.setText("Each line is an alternative; ranks use average positions for ties. Direction defaults are inferred from column names and can be adjusted in the score chart.")

    def _draw_rank_correlation(self, method):
        d=self.state.data; values=np.asarray(d.ranking_values,float)
        if values.shape[1]<2:
            self.lbl_note.setText("Import at least two numeric method/result columns to compare rankings."); return
        result=pairwise_rank_correlations(values,d.ranking_columns)
        matrix=result[method]
        names=[name if len(name)<=14 else name[:12]+"…" for name in d.ranking_columns]
        n=len(names)
        image=pg.ImageItem(matrix.T)
        image.setLookupTable(pg.colormap.get("viridis").getLookupTable(0.0,1.0,256))
        image.setLevels([-1,1]); image.setRect(QRectF(0,0,n,n)); self.plot.addItem(image)
        ticks=[[(i+.5,name) for i,name in enumerate(names)]]
        self.plot.getAxis("bottom").setTicks(ticks); self.plot.getAxis("left").setTicks(ticks)
        for row in range(n):
            for col in range(n):
                value=matrix[row,col]
                label="NA" if not np.isfinite(value) else f"{value:.2f}"
                item=pg.TextItem(label,color="white" if np.isfinite(value) and abs(value)>.48 else "#172033",anchor=(.5,.5))
                item.setPos(col+.5,row+.5); self.plot.addItem(item)
        self.plot.setLabel("bottom","Ranking method / result column")
        self.plot.setLabel("left","Ranking method / result column")
        label="Spearman ρ" if method=="spearman" else "Kendall τ-b"
        self.lbl_note.setText(f"{label} calculated from within-column ranks. Diagonal = 1; direction defaults: lower is better for rank, distance-to-ideal, cost, error, loss, and D+ columns.")

    def export_figure(self):
        path, selected = QFileDialog.getSaveFileName(self,"Export figure","figure.png","PNG image (*.png);;SVG vector image (*.svg)")
        if not path:return
        try:
            is_svg = path.lower().endswith(".svg") or selected.startswith("SVG")
            if is_svg:
                if path.lower().endswith(".png"): path = path[:-4]
                if not path.lower().endswith(".svg"): path += ".svg"
                exp=SVGExporter(self.plot.plotItem); exp.export(path)
            else:
                if path.lower().endswith(".svg"): path = path[:-4]
                if not path.lower().endswith(".png"): path += ".png"
                exp=ImageExporter(self.plot.plotItem)
                width,ok=QInputDialog.getInt(self,"PNG export","Image width (pixels)",2400,800,8000,200)
                if not ok:return
                exp.parameters()["width"]=width
                exp.parameters()["background"]="w"
                exp.export(path)
            QMessageBox.information(self,"Export complete",f"Figure saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self,"Export failed",str(exc))
