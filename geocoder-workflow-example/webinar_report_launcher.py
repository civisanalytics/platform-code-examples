"""
report.py - Harris County Food Access and Demographics

Single-file HTML report for a Civis Platform Python Script (no GitHub
connection required). Organized top to bottom: imports, constants,
templates, then classes and functions. See CLAUDE.md for the conventions
this keeps even with everything in one file - most importantly: templates
use str.format(), not Jinja (not installed on Civis Platform's plain Python
Script environment), so any conditional or repeated markup gets assembled
into a plain string in Python (inside get_context()) before it's dropped
into a template placeholder.

Run locally: python report.py
Publish: paste this whole file into a Civis Platform Python Script and run
it there - see README.md.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any

import civis
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPORT_DIR = Path(__file__).resolve().parent
OUTPUT_FILENAME = "harris_county_food_access_report.html"

REPORT_NAME = "Harris County Food Access and Demographics"
REPORT_DESCRIPTION = (
    "Census tract demographics for Harris County, Texas, from the 2020-2024 "
    "American Community Survey, mapped alongside SNAP-authorized retailer "
    "locations. Shade the map by any of 30 demographic measures to see where "
    "need and food access diverge."
)

# The Civis Platform database this report's data lives in. Named DB_NAME,
# not DATABASE_NAME - "database" is a reserved word for Civis Platform
# environment variables.
DB_NAME = "postgis-general"

TRACT_TABLE = "public.tx_2024_tiger_shapefile"
ACS_TABLE = "public.acs_5yr_2024_tract_profile"

# SNAP retailers arrive in two tables, the same split the Civis geocoder
# produces: the geocoded output carries the primary key plus appended
# coordinates, and the descriptive fields stay behind in the source table.
# They join on primary_key.
STORE_GEO_TABLE = "public.historical_snap_retailer_locator_post_geocode_run1_clean"
STORE_ATTR_TABLE = "public.historical_snap_retailer_locator_pre_cass"

# Columns of STORE_ATTR_TABLE, which is known:
#   primary_key, address_line_1, address_line_2, city, state, zip,
#   store_name, store_type, zip4, county, end_date
ATTR_KEY = "primary_key"
ATTR_NAME = "store_name"
ATTR_TYPE = "store_type"
ATTR_ADDRESS = "address_line_1"
ATTR_CITY = "city"
ATTR_END_DATE = "end_date"

# This is a historical file, so it includes retailers whose SNAP
# authorization has ended. A closed store is not food access, so rows with an
# end date in the past are excluded from the map and counted separately.
# Set False to plot every retailer the file has ever contained.
OPEN_STORES_ONLY = True

# Harris County, Texas.
STATE_FIPS = "48"
COUNTY_FIPS = "201"
COUNTY_LABEL = "Harris County, Texas"

# Tolerance for ST_SimplifyPreserveTopology, in degrees. Roughly 11 metres.
# Full-resolution TIGER tract polygons are far more detailed than a
# county-wide map can show, and the whole geometry has to be embedded in this
# HTML file, so it gets thinned. PreserveTopology (rather than plain
# ST_Simplify) keeps shared borders between neighbouring tracts matching -
# without it, adjacent tracts thin independently and the map fills with
# slivers and gaps.
SIMPLIFY_TOLERANCE = 0.0001

# Decimal places kept on each emitted coordinate. ST_AsGeoJSON defaults to 15,
# which is nanometre precision and roughly doubles the payload for no visible
# benefit. Five decimal places is about 1 metre at this latitude.
COORD_DECIMALS = 5

# Which demographic columns can shade the map, in the order they appear in
# the dropdown. `fmt` drives both the legend and the popup:
#   pct      - one decimal, trailing %
#   money    - whole dollars, thousands separators
#   count    - whole number, thousands separators
#   decimal1 - one decimal, optional suffix
#   decimal2 - two decimals, optional suffix
MAP_VARIABLES: list[dict[str, str]] = [
    {"col": "pct_below_poverty", "label": "Below poverty", "fmt": "pct", "group": "Income"},
    {"col": "median_household_income", "label": "Median household income", "fmt": "money", "group": "Income"},
    {"col": "per_capita_income", "label": "Per capita income", "fmt": "money", "group": "Income"},
    {"col": "pct_housing_cost_burdened", "label": "Housing cost burdened", "fmt": "pct", "group": "Income"},
    {"col": "pct_unemployed", "label": "Unemployed", "fmt": "pct", "group": "Work"},
    {"col": "pct_employed", "label": "Employed", "fmt": "pct", "group": "Work"},
    {"col": "pct_in_labor_force", "label": "In labor force", "fmt": "pct", "group": "Work"},
    {"col": "total_population", "label": "Total population", "fmt": "count", "group": "Population"},
    {"col": "median_age", "label": "Median age", "fmt": "decimal1", "suffix": " yrs", "group": "Population"},
    {"col": "pct_under_18", "label": "Under 18", "fmt": "pct", "group": "Population"},
    {"col": "pct_65_plus", "label": "65 and over", "fmt": "pct", "group": "Population"},
    {"col": "pct_with_disability", "label": "With a disability", "fmt": "pct", "group": "Population"},
    {"col": "pct_veterans", "label": "Veterans", "fmt": "pct", "group": "Population"},
    {"col": "pct_hispanic", "label": "Hispanic", "fmt": "pct", "group": "Race and ethnicity"},
    {"col": "pct_white_nh", "label": "White, non-Hispanic", "fmt": "pct", "group": "Race and ethnicity"},
    {"col": "pct_black_nh", "label": "Black, non-Hispanic", "fmt": "pct", "group": "Race and ethnicity"},
    {"col": "pct_asian_nh", "label": "Asian, non-Hispanic", "fmt": "pct", "group": "Race and ethnicity"},
    {"col": "pct_other_race_nh", "label": "Other race, non-Hispanic", "fmt": "pct", "group": "Race and ethnicity"},
    {"col": "pct_limited_english_households", "label": "Limited English households", "fmt": "pct", "group": "Race and ethnicity"},
    {"col": "pct_bachelors_or_higher", "label": "Bachelor's degree or higher", "fmt": "pct", "group": "Education"},
    {"col": "total_households", "label": "Total households", "fmt": "count", "group": "Households"},
    {"col": "avg_household_size", "label": "Average household size", "fmt": "decimal2", "suffix": " people", "group": "Households"},
    {"col": "pct_family_households", "label": "Family households", "fmt": "pct", "group": "Households"},
    {"col": "pct_families_with_children", "label": "Families with children", "fmt": "pct", "group": "Households"},
    {"col": "pct_single_parent_families", "label": "Single parent families", "fmt": "pct", "group": "Households"},
    {"col": "pct_owner_occupied", "label": "Owner occupied", "fmt": "pct", "group": "Housing"},
    {"col": "median_home_value", "label": "Median home value", "fmt": "money", "group": "Housing"},
    {"col": "median_gross_rent", "label": "Median gross rent", "fmt": "money", "group": "Housing"},
    {"col": "pct_broadband", "label": "Broadband access", "fmt": "pct", "group": "Housing"},
    {"col": "pct_same_house_1yr", "label": "Same house one year ago", "fmt": "pct", "group": "Mobility"},
    {"col": "pct_moved_from_different_state", "label": "Moved from another state", "fmt": "pct", "group": "Mobility"},
]

DEFAULT_MAP_VARIABLE = "pct_below_poverty"

# Candidate column names for the SNAP retailer table, most specific first.
# The table's exact schema isn't known ahead of time, so discover_store_columns()
# resolves these against information_schema at run time and fails loudly with
# the real column list if none match.
STORE_LAT_CANDIDATES = ["civis_latitude", "latitude", "lat", "y"]
STORE_LON_CANDIDATES = ["civis_longitude", "longitude", "longtitude", "lon", "lng", "long", "x"]
# The join key on the geocoded table. The Civis geocoder passes through
# whichever primary key the job was configured with, so the name can vary.
STORE_KEY_CANDIDATES = ["primary_key", "primarykey", "record_id", "id", "store_id"]

# ---------------------------------------------------------------------------
# Templates - plain Python strings, filled in with str.format(), not Jinja.
# Any {% if %}/{% for %}-style logic Jinja would normally handle here
# instead happens in Python, inside each class's get_context() - see
# CLAUDE.md. Conditional/repeated markup arrives already assembled as a
# single placeholder (e.g. subtitle_html, children_html), never built
# inside these strings themselves.
#
# MAP_JS below is a template-section constant that is never itself passed
# through str.format(), which is why its JavaScript braces are written
# normally. It reaches the page as a single {map_js} placeholder.
# ---------------------------------------------------------------------------

STYLES_CSS = """
/* Civis Analytics brand colors, applied in the practical dashboard style
   used across existing Civis HTML reports. Colors: Navy #215470,
   Night #0A2138, Night Gray #4B5563, Teal #0097A7, Amber #F1A137,
   Blue #058DC7. Inline (<style> in the page itself, not a linked
   stylesheet) since this report has no separate static-assets location. */

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #F8FAFC;
  color: #334155;
}

.report-header {
  background: #0A2138;
  color: #F1F5F9;
  padding: 20px 32px;
}

.report-header h1 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0;
}

.report-subtitle {
  font-size: 0.8rem;
  color: #94A3B8;
  margin-top: 4px;
}

.report-body {
  padding: 28px 32px;
  max-width: 1400px;
  margin: 0 auto;
}

.section {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  padding: 22px 24px;
  margin-bottom: 24px;
}

.section-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: #1E293B;
  margin: 0 0 12px;
}

.section-body p {
  font-size: 0.9rem;
  line-height: 1.5;
  color: #334155;
}

.card {
  display: inline-block;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  padding: 16px 20px;
  min-width: 200px;
  margin: 0 16px 24px 0;
  vertical-align: top;
}

.card-label {
  font-size: 0.85rem;
  color: #64748B;
  font-weight: 500;
}

.card-value {
  font-size: 1.75rem;
  font-weight: 600;
  color: #1E293B;
  margin-top: 6px;
}

.card-note {
  font-size: 0.72rem;
  color: #94A3B8;
  margin-top: 6px;
}

.report-footer {
  padding: 16px 32px;
  color: #94A3B8;
  font-size: 0.75rem;
}

/* Map */

.map-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 14px;
}

.map-controls label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #4B5563;
}

.map-controls select {
  font: inherit;
  font-size: 0.85rem;
  padding: 6px 10px;
  border: 1px solid #D1D5DB;
  border-radius: 6px;
  background: #FFFFFF;
  color: #1E293B;
  min-width: 260px;
}

.map-toggle {
  font-size: 0.8rem;
  color: #4B5563;
  display: flex;
  align-items: center;
  gap: 6px;
}

#map {
  height: 620px;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

.map-fallback {
  padding: 18px 20px;
  background: #FEF3C7;
  border: 1px solid #F1A137;
  border-radius: 6px;
  font-size: 0.85rem;
  color: #78350F;
}

.legend {
  margin-top: 14px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 18px;
  font-size: 0.75rem;
  color: #4B5563;
}

.legend-title {
  font-weight: 600;
  color: #1E293B;
  margin-right: 4px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-swatch {
  width: 16px;
  height: 12px;
  border: 1px solid rgba(10, 33, 56, 0.18);
  display: inline-block;
}

.legend-store-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #F1A137;
  border: 1.5px solid #FFFFFF;
  box-shadow: 0 0 0 1px rgba(10, 33, 56, 0.35);
  display: inline-block;
}

.tract-popup {
  font-size: 0.8rem;
  line-height: 1.5;
}

.tract-popup .tract-popup-name {
  font-weight: 700;
  color: #0A2138;
  display: block;
  margin-bottom: 4px;
}

.tract-popup .tract-popup-value {
  font-size: 1.05rem;
  font-weight: 600;
  color: #215470;
}

.tract-popup .store-addr {
  color: #64748B;
  font-size: 0.75rem;
}
"""

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{report_title}</title>
  {head_extra}
  <style>{styles_css}</style>
</head>
<body>

  <header class="report-header">
    <h1>{report_title}</h1>
    {subtitle_html}
  </header>

  <main class="report-body">
    {children_html}
  </main>

  <footer class="report-footer">
    <p>{footer_text}</p>
  </footer>

</body>
</html>
"""

SECTION_TEMPLATE = """<section class="section">
  {title_html}
  <div class="section-body">
    {body_html}
    {children_html}
  </div>
</section>
"""

CARD_TEMPLATE = """<div class="card">
  {label_html}
  <div class="card-value">{value}</div>
  {note_html}
</div>
"""

MAP_SECTION_TEMPLATE = """<section class="section">
  {title_html}
  <div class="section-body">
    {body_html}
    <div class="map-controls">
      <label for="map-variable">Shade tracts by</label>
      <select id="map-variable">{options_html}</select>
      <span class="map-toggle">
        <input type="checkbox" id="toggle-stores" checked>
        <label for="toggle-stores">Show SNAP retailers</label>
      </span>
    </div>
    <div id="map"></div>
    <div class="legend" id="map-legend"></div>
  </div>
  <script>window.REPORT_DATA = {data_json};</script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
  <script>{map_js}</script>
</section>
"""

MAP_JS = """
(function () {
  var data = window.REPORT_DATA;
  var container = document.getElementById('map');

  if (typeof L === 'undefined') {
    container.outerHTML =
      '<div class="map-fallback"><strong>The map could not load.</strong> ' +
      'Leaflet is served from cdnjs.cloudflare.com and the browser could not ' +
      'reach it. The figures above are unaffected. If this persists, the ' +
      'published report may be blocking external scripts.</div>';
    return;
  }

  var RAMP = ['#EAF1F7', '#C3D9E8', '#8FB9D6', '#5795BF', '#2C6D9E', '#215470'];
  var NO_DATA = '#E5E7EB';

  var meta = {};
  data.variables.forEach(function (v) { meta[v.col] = v; });

  function fmt(value, m) {
    if (value === null || value === undefined || isNaN(value)) return 'No data';
    var suffix = m.suffix || '';
    if (m.fmt === 'pct') return value.toFixed(1) + '%';
    if (m.fmt === 'money') {
      return '$' + Math.round(value).toLocaleString('en-US');
    }
    if (m.fmt === 'count') return Math.round(value).toLocaleString('en-US');
    if (m.fmt === 'decimal1') return value.toFixed(1) + suffix;
    if (m.fmt === 'decimal2') return value.toFixed(2) + suffix;
    return String(value);
  }

  function breaksFor(col) {
    var vals = [];
    data.tracts.features.forEach(function (f) {
      var v = f.properties[col];
      if (v !== null && v !== undefined && !isNaN(v)) vals.push(Number(v));
    });
    if (!vals.length) return null;
    vals.sort(function (a, b) { return a - b; });
    if (vals[0] === vals[vals.length - 1]) return null;
    var cuts = [];
    for (var i = 1; i < RAMP.length; i++) {
      var pos = (vals.length - 1) * (i / RAMP.length);
      var lo = Math.floor(pos);
      var hi = Math.ceil(pos);
      cuts.push(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo));
    }
    return { min: vals[0], max: vals[vals.length - 1], cuts: cuts };
  }

  function colorFor(value, br) {
    if (value === null || value === undefined || isNaN(value)) return NO_DATA;
    if (!br) return RAMP[Math.floor(RAMP.length / 2)];
    for (var i = 0; i < br.cuts.length; i++) {
      if (value < br.cuts[i]) return RAMP[i];
    }
    return RAMP[RAMP.length - 1];
  }

  var map = L.map('map', { scrollWheelZoom: false });
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors, &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  var currentCol = data.default_variable;
  var currentBreaks = breaksFor(currentCol);

  function styleFor(feature) {
    return {
      fillColor: colorFor(feature.properties[currentCol], currentBreaks),
      fillOpacity: 0.82,
      color: '#FFFFFF',
      weight: 0.6
    };
  }

  function popupHtml(props) {
    var m = meta[currentCol];
    var lines = '<span class="tract-popup-name">' + (props.tract_name || props.geoid) + '</span>';
    lines += m.label + ': <span class="tract-popup-value">' +
      fmt(props[currentCol], m) + '</span><br>';
    lines += 'Population: ' + fmt(props.total_population, { fmt: 'count' }) + '<br>';
    lines += 'SNAP retailers in tract: ' + (props.store_count || 0);
    return '<div class="tract-popup">' + lines + '</div>';
  }

  var tractLayer = L.geoJSON(data.tracts, {
    style: styleFor,
    onEachFeature: function (feature, layer) {
      layer.bindPopup(function () { return popupHtml(feature.properties); });
      layer.on('mouseover', function () { layer.setStyle({ weight: 2, color: '#0A2138' }); });
      layer.on('mouseout', function () { layer.setStyle({ weight: 0.6, color: '#FFFFFF' }); });
    }
  }).addTo(map);

  map.fitBounds(tractLayer.getBounds(), { padding: [12, 12] });

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function storePopupHtml(s) {
    var html = '<div class="tract-popup"><span class="tract-popup-name">' +
      escapeHtml(s.name || 'SNAP retailer (unnamed)') + '</span>';
    if (s.type) html += escapeHtml(s.type) + '<br>';
    if (s.addr) html += '<span class="store-addr">' + escapeHtml(s.addr) + '</span>';
    return html + '</div>';
  }

  var storeLayer = L.layerGroup();
  data.stores.forEach(function (s) {
    var marker = L.circleMarker([s.lat, s.lon], {
      radius: 4,
      fillColor: '#F1A137',
      fillOpacity: 0.95,
      color: '#FFFFFF',
      weight: 1
    }).bindPopup(storePopupHtml(s));
    if (s.name) marker.bindTooltip(escapeHtml(s.name), { direction: 'top' });
    marker.addTo(storeLayer);
  });
  storeLayer.addTo(map);

  function renderLegend() {
    var m = meta[currentCol];
    var el = document.getElementById('map-legend');
    var html = '<span class="legend-title">' + m.label + '</span>';
    if (!currentBreaks) {
      html += '<span class="legend-item">Not enough variation to classify</span>';
    } else {
      var edges = [currentBreaks.min].concat(currentBreaks.cuts).concat([currentBreaks.max]);
      for (var i = 0; i < RAMP.length; i++) {
        html += '<span class="legend-item">' +
          '<span class="legend-swatch" style="background:' + RAMP[i] + '"></span>' +
          fmt(edges[i], m) + ' to ' + fmt(edges[i + 1], m) + '</span>';
      }
    }
    html += '<span class="legend-item">' +
      '<span class="legend-swatch" style="background:' + NO_DATA + '"></span>No data</span>';
    if (data.stores.length) {
      html += '<span class="legend-item"><span class="legend-store-dot"></span>' +
        'SNAP retailer (' + data.stores.length.toLocaleString('en-US') + ')</span>';
    }
    el.innerHTML = html;
  }

  document.getElementById('map-variable').addEventListener('change', function (e) {
    currentCol = e.target.value;
    currentBreaks = breaksFor(currentCol);
    tractLayer.setStyle(styleFor);
    tractLayer.eachLayer(function (layer) { layer.closePopup(); });
    renderLegend();
  });

  document.getElementById('toggle-stores').addEventListener('change', function (e) {
    if (e.target.checked) storeLayer.addTo(map);
    else map.removeLayer(storeLayer);
  });

  renderLegend();
})();
"""

TEMPLATES: dict[str, str] = {
    "report": REPORT_TEMPLATE,
    "section": SECTION_TEMPLATE,
    "card": CARD_TEMPLATE,
    "map_section": MAP_SECTION_TEMPLATE,
}

# ---------------------------------------------------------------------------
# Classes and functions
# ---------------------------------------------------------------------------


def load_sql(sql: str, database: str) -> pd.DataFrame:
    """Run `sql` against a Civis Platform database and return the result as
    a DataFrame. Thin wrapper around civis.io.read_civis_sql - `database` is
    project-specific (see DB_NAME above); this function stays generic."""
    return civis.io.read_civis_sql(sql, database=database, return_as="pandas")


def ensure_report_id_param(client: civis.APIClient, job_id: int) -> None:
    """Make sure this Python Script has a REPORT_ID parameter defined,
    adding it if it's missing. Civis Platform requires a parameter to be
    declared via `params` before an `arguments` value for that key is
    recognized - passing arguments={"REPORT_ID": ...} to patch_python3
    without REPORT_ID ever appearing in `params` does not create a usable
    script parameter (see Civis's Script Parameters docs: `params` defines
    the parameter, `arguments` sets its value for a parameter that already
    exists). Without this, the REPORT_ID argument set below never turns
    into an environment variable on the next run, so publish_report() would
    take the "create new report" branch every run instead of updating the
    same report. This only ensures the parameter definition exists; it does
    not set a value - the patch_python3(arguments=...) call right after it
    still does that."""
    script = client.scripts.get_python3(job_id)
    existing_params = [dict(p) for p in (script.params or [])]
    if any(p.get("name") == "REPORT_ID" for p in existing_params):
        return
    client.scripts.patch_python3(
        id=job_id,
        params=existing_params + [
            {"name": "REPORT_ID", "type": "integer", "required": False}
        ],
    )


def publish_report(
    html: str,
    report_name: str,
    report_desc: str,
    local_filename: str,
) -> None:
    """Publish `html` as a Civis Platform report if running inside a Civis
    Python Script (CIVIS_JOB_ID is set), updating the existing report if
    REPORT_ID is also set, else creating a new one. Outside a Civis job (e.g.
    local development), just write `html` to `local_filename` instead.

    Uses the Python Script API (patch_python3 / post_python3_runs_outputs),
    not the Container Script one - same CIVIS_JOB_ID/CIVIS_RUN_ID/REPORT_ID
    pattern, different endpoints, because this runs as a Civis Platform
    Python Script rather than a Container Script."""
    job_id = os.environ.get("CIVIS_JOB_ID")
    if job_id:
        client = civis.APIClient()
        job_id = int(job_id)
        run_id = int(os.environ["CIVIS_RUN_ID"])
        existing_id = os.environ.get("REPORT_ID")

        if existing_id:
            print(f"Updating existing Civis report {existing_id}...")
            report = client.reports.patch(
                id=int(existing_id), name=report_name, code_body=html
            )
        else:
            print("Creating new Civis report...")
            report = client.reports.post(
                name=report_name, description=report_desc, code_body=html
            )
            ensure_report_id_param(client, job_id)
            client.scripts.patch_python3(
                id=job_id, arguments={"REPORT_ID": int(report.id)}
            )

        client.scripts.post_python3_runs_outputs(job_id, run_id, "Report", report.id)
        print(f"Done. Report id: {report.id}")
    else:
        with open(local_filename, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Done. Written to {local_filename}")


class HtmlRender:
    """Base class for anything that renders itself to an HTML string.
    Same composite pattern as the multi-file version of this skill: each
    instance holds its own data and any child HtmlRender instances; render()
    renders children first (bottom-up), then fills in this instance's own
    template (from TEMPLATES) with get_context()'s output via str.format()."""

    template_name: str = ""

    def __init__(
        self,
        data: Any = None,
        children: list["HtmlRender"] | None = None,
        template_name: str | None = None,
        **context: Any,
    ) -> None:
        self.data = data
        self.children = children or []
        self.template_name = template_name or self.template_name
        self.context = context

    def get_context(self) -> dict:
        """Return the template variables for this instance. Default: pass
        through whatever kwargs were given at construction time. Override
        and call super().get_context() first, then add/override keys
        computed from self.data - including building any conditional HTML
        fragments (e.g. title_html) this instance's template needs, since
        str.format() can't do that itself."""
        return dict(self.context)

    def render(self) -> str:
        """Render children (bottom-up) into one joined HTML string, then
        fill in this instance's own template with that plus get_context()'s
        output."""
        children_html = "\n".join(child.render() for child in self.children)
        context = self.get_context()
        context.setdefault("children_html", children_html)
        context.setdefault("data", self.data)
        return TEMPLATES[self.template_name].format(**context)


class Card(HtmlRender):
    """Smallest building block - a single stat or short block of content.
    Paired with the "card" template by default."""

    template_name = "card"


class Section(HtmlRender):
    """A block of text and/or a group of cards (or nested sections), under
    an optional heading. Paired with the "section" template by default."""

    template_name = "section"


class Report(HtmlRender):
    """The whole page. Takes report_title/report_subtitle plus a list of
    children (Sections, Cards, or a mix) rendered in order. Paired with the
    "report" template by default."""

    template_name = "report"

    def get_context(self) -> dict:
        context = super().get_context()
        report_subtitle = context.pop("report_subtitle", None)
        context["subtitle_html"] = (
            f'<p class="report-subtitle">{report_subtitle}</p>' if report_subtitle else ""
        )
        context.setdefault("styles_css", STYLES_CSS)
        # Leaflet's stylesheet has to be a linked absolute reference in
        # <head>; Civis Platform reports expect external CSS and JS to come
        # from a CDN rather than being hosted alongside the report.
        context.setdefault(
            "head_extra",
            '<link rel="stylesheet" '
            'href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">',
        )
        context.setdefault("footer_text", "Generated by report.py")
        return context


class MetricCard(Card):
    """A single labeled number, optionally with a small note underneath.
    `value` is passed in already formatted - formatting decisions belong in
    build_report(), where the data and its units are both in hand."""

    def get_context(self) -> dict:
        context = super().get_context()
        label = context.pop("label", None)
        note = context.pop("note", None)
        context["label_html"] = f'<div class="card-label">{label}</div>' if label else ""
        context["note_html"] = f'<div class="card-note">{note}</div>' if note else ""
        context["value"] = self.data
        return context


class TextSection(Section):
    """A heading plus a block of text, or a heading plus child cards."""

    def get_context(self) -> dict:
        context = super().get_context()
        title = context.pop("title", None)
        context["title_html"] = f'<h2 class="section-title">{title}</h2>' if title else ""
        body = self.data
        context["body_html"] = f"<p>{body}</p>" if body else ""
        return context


class MapSection(Section):
    """The choropleth. self.data is a dict with three keys:
    `tracts` (a GeoJSON FeatureCollection), `stores` (a list of point dicts),
    and `variables` (the MAP_VARIABLES entries actually present in the data).

    The variable dropdown, the colour scale, the legend, and the popups are
    all rebuilt client side when the selection changes, so every measure is
    available without another query - but only one is ever shaded at a time,
    since two overlaid colour scales on the same polygons can't be read."""

    template_name = "map_section"

    def get_context(self) -> dict:
        context = super().get_context()
        title = context.pop("title", None)
        body = context.pop("body", None)
        context["title_html"] = f'<h2 class="section-title">{title}</h2>' if title else ""
        context["body_html"] = f"<p>{body}</p>" if body else ""

        # The <select> is built here rather than in the template because
        # str.format() has no loop of its own. Grouped with <optgroup> so 31
        # measures stay navigable.
        options: list[str] = []
        current_group = None
        for var in self.data["variables"]:
            group = var.get("group", "Other")
            if group != current_group:
                if current_group is not None:
                    options.append("</optgroup>")
                options.append(f'<optgroup label="{group}">')
                current_group = group
            selected = " selected" if var["col"] == DEFAULT_MAP_VARIABLE else ""
            options.append(
                f'<option value="{var["col"]}"{selected}>{var["label"]}</option>'
            )
        if current_group is not None:
            options.append("</optgroup>")
        context["options_html"] = "".join(options)

        context["data_json"] = json.dumps(
            {
                "tracts": self.data["tracts"],
                "stores": self.data["stores"],
                "variables": self.data["variables"],
                "default_variable": DEFAULT_MAP_VARIABLE,
            },
            separators=(",", ":"),
        )
        context["map_js"] = MAP_JS
        return context


def discover_store_columns() -> dict[str, str]:
    """Resolve the latitude, longitude, and join-key columns on the geocoded
    SNAP retailer table.

    Only these three come from the geocoded table. Store names, types, and
    addresses live in STORE_ATTR_TABLE, whose columns are known and named in
    the ATTR_* constants above, so they need no discovery.

    All three roles are required. If any is missing this raises with the
    table's real column list. That list is printed on every run either way,
    so a wrong guess is visible in the run log.
    """
    schema, table = STORE_GEO_TABLE.split(".", 1)
    schema_df = load_sql(
        "SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
        "ORDER BY ordinal_position",
        database=DB_NAME,
    )
    columns = schema_df["column_name"].tolist()

    print(f"{STORE_GEO_TABLE} columns: {list(zip(columns, schema_df['data_type']))}")

    lookup = {c.lower(): c for c in columns}

    def first_match(candidates: list[str]) -> str | None:
        for candidate in candidates:
            if candidate in lookup:
                return lookup[candidate]
        return None

    resolved = {
        "lat": first_match(STORE_LAT_CANDIDATES),
        "lon": first_match(STORE_LON_CANDIDATES),
        "key": first_match(STORE_KEY_CANDIDATES),
    }

    missing = [role for role, col in resolved.items() if not col]
    if missing:
        raise RuntimeError(
            f"Could not resolve {missing} on {STORE_GEO_TABLE}.\n"
            f"Latitude candidates: {STORE_LAT_CANDIDATES}\n"
            f"Longitude candidates: {STORE_LON_CANDIDATES}\n"
            f"Join key candidates: {STORE_KEY_CANDIDATES}\n"
            f"The table's actual columns are: {columns}\n"
            "Add the right names to the matching *_CANDIDATES list above."
        )

    print(f"Resolved geocoded-table columns: {resolved}")
    return resolved


def get_tracts() -> pd.DataFrame:
    """One row per census tract in Harris County, Texas (state FIPS 48,
    county FIPS 201), with its simplified boundary and all 30 demographic
    measures from the 2020-2024 ACS tract profile.

    Geometry comes from the TIGER shapefile table and is thinned with
    ST_SimplifyPreserveTopology at SIMPLIFY_TOLERANCE degrees, then emitted
    as GeoJSON so the browser can consume it without a WKT parser. The join
    to the ACS profile is a LEFT JOIN on tract GEOID, so a tract with no ACS
    row still appears on the map, shaded as "No data", rather than silently
    vanishing from the county outline.
    """
    demographic_cols = ",\n            ".join(
        f"b.{var['col']}" for var in MAP_VARIABLES
    )
    sql = f"""
        SELECT
            a.geoid,
            a.statefp,
            a.countyfp,
            b.tract_name,
            ST_AsGeoJSON(
                ST_SimplifyPreserveTopology(a.geom, {SIMPLIFY_TOLERANCE}),
                {COORD_DECIMALS}
            ) AS geom_json,
            {demographic_cols}
        FROM {TRACT_TABLE} a
        LEFT JOIN {ACS_TABLE} b
               ON a.geoid = b.census_tract_geoid
        WHERE a.statefp = '{STATE_FIPS}'
          AND a.countyfp = '{COUNTY_FIPS}'
        ORDER BY a.geoid
    """
    return load_sql(sql, database=DB_NAME)


def get_stores(store_cols: dict[str, str]) -> pd.DataFrame:
    """Every SNAP retailer whose geocoded point falls inside a Harris County
    census tract, with its name, type, address, SNAP authorization end date,
    and the GEOID of the tract containing it.

    Two tables. The geocoded table supplies the join key and the coordinates;
    the pre-CASS source table supplies the descriptive fields. They are
    joined on the primary key, which is what the geocoder passes through. The
    join is an inner join on purpose: a coordinate with no matching source
    row has nothing to label it with, and a source row with no coordinate
    cannot be mapped.

    County membership is decided spatially rather than by trusting the
    source table's `county` column: ST_Contains against the TIGER tract
    polygons for state FIPS 48 / county FIPS 201. The point is built from the
    retailer's latitude and longitude as EPSG:4326 and transformed into
    whatever SRID the shapefile actually uses, because TIGER data is commonly
    NAD83 (EPSG:4269) and ST_Contains requires both sides to share an SRID.

    Rows with a null latitude or longitude are excluded here - those failed
    to geocode and cannot be placed on a map. `end_date` is returned raw and
    filtered in Python (see filter_open_stores) rather than in SQL, so this
    query makes no assumption about whether it is a date or a text column.
    """
    sql = f"""
        SELECT
            a.{ATTR_NAME}    AS store_name,
            a.{ATTR_TYPE}    AS store_type,
            a.{ATTR_ADDRESS} AS store_address,
            a.{ATTR_CITY}    AS store_city,
            a.{ATTR_END_DATE} AS end_date,
            g.{store_cols['lat']} AS lat,
            g.{store_cols['lon']} AS lon,
            t.geoid AS tract_geoid
        FROM {STORE_GEO_TABLE} g
        JOIN {STORE_ATTR_TABLE} a
          ON a.{ATTR_KEY} = g.{store_cols['key']}
        JOIN {TRACT_TABLE} t
          ON ST_Contains(
                 t.geom,
                 ST_Transform(
                     ST_SetSRID(
                         ST_MakePoint(g.{store_cols['lon']}, g.{store_cols['lat']}),
                         4326
                     ),
                     ST_SRID(t.geom)
                 )
             )
        WHERE t.statefp = '{STATE_FIPS}'
          AND t.countyfp = '{COUNTY_FIPS}'
          AND g.{store_cols['lat']} IS NOT NULL
          AND g.{store_cols['lon']} IS NOT NULL
    """
    return load_sql(sql, database=DB_NAME)


def filter_open_stores(stores: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Split the retailers into those still SNAP-authorized and a count of
    those whose authorization has ended.

    This is a historical file, so it contains stores that have closed or lost
    authorization. A closed store is not food access, and leaving it on the
    map would overstate coverage in exactly the tracts this report is meant
    to flag. A row counts as open if `end_date` is null or parses to a date
    that has not passed. Dates are parsed permissively, and anything
    unparseable is treated as open rather than silently dropped, so a format
    surprise cannot quietly delete retailers from the map.

    Returns (open_stores, closed_count). If OPEN_STORES_ONLY is False,
    everything is returned as open and the count is still reported.
    """
    if "end_date" not in stores.columns:
        return stores, 0

    # Mixed and unparseable date formats are expected here and handled below,
    # so pandas' per-element format-inference warning is just log noise.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(stores["end_date"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    closed = parsed.notna() & (parsed < today)
    closed_count = int(closed.sum())

    unparseable = stores["end_date"].notna() & parsed.isna()
    if unparseable.any():
        print(
            f"Note: {int(unparseable.sum()):,} retailer(s) have an end_date that "
            "could not be parsed as a date. They are treated as still open. "
            f"Example value: {stores.loc[unparseable, 'end_date'].iloc[0]!r}"
        )

    if not OPEN_STORES_ONLY:
        print(f"OPEN_STORES_ONLY is False, so all {len(stores):,} retailers are mapped.")
        return stores, closed_count

    print(
        f"Excluding {closed_count:,} retailer(s) whose SNAP authorization has ended; "
        f"{len(stores) - closed_count:,} remain."
    )
    return stores.loc[~closed].copy(), closed_count


def build_map_data(tracts: pd.DataFrame, stores: pd.DataFrame) -> dict:
    """Turn the two query results into the payload the map needs: a GeoJSON
    FeatureCollection whose properties carry every demographic measure plus
    a per-tract SNAP retailer count, and a flat list of store points.

    Tracts whose geometry failed to parse are dropped and reported, rather
    than being allowed to break the whole map."""
    stores_per_tract = stores.groupby("tract_geoid").size().to_dict()

    present = [v for v in MAP_VARIABLES if v["col"] in tracts.columns]
    missing = [v["col"] for v in MAP_VARIABLES if v["col"] not in tracts.columns]
    if missing:
        print(f"Warning: these columns were not returned and will be skipped: {missing}")

    features = []
    skipped = 0
    for row in tracts.to_dict("records"):
        raw = row.get("geom_json")
        if not raw:
            skipped += 1
            continue
        try:
            geometry = json.loads(raw)
        except (TypeError, ValueError):
            skipped += 1
            continue

        props: dict[str, Any] = {
            "geoid": row["geoid"],
            "tract_name": row.get("tract_name") or f"Tract {row['geoid']}",
            "store_count": int(stores_per_tract.get(row["geoid"], 0)),
        }
        for var in present:
            value = row.get(var["col"])
            # Rounded to two decimals: every measure here is displayed at one
            # or two decimals at most, and the full float repr of a numeric
            # column adds up over 1,100 tracts times 31 measures.
            props[var["col"]] = None if pd.isna(value) else round(float(value), 2)

        features.append({"type": "Feature", "geometry": geometry, "properties": props})

    if skipped:
        print(f"Warning: {skipped} tract(s) had unusable geometry and were dropped.")

    def clean(value: Any) -> str | None:
        """Null-safe string, treating blanks and literal 'nan' as missing."""
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    store_points = []
    for r in stores.to_dict("records"):
        if pd.isna(r["lat"]) or pd.isna(r["lon"]):
            continue
        address = clean(r.get("store_address"))
        city = clean(r.get("store_city"))
        # Prefer the store's own name. Fall back to its address so a dot is
        # still identifiable, and only then to nothing, which the map renders
        # as a generic label.
        point = {
            "name": clean(r.get("store_name")) or address,
            "type": clean(r.get("store_type")),
            "addr": ", ".join(p for p in (address, city) if p) or None,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
        }
        # Don't repeat the address as both the title and the subtitle.
        if point["name"] == address and point["addr"] == address:
            point["addr"] = city
        store_points.append(point)

    named = sum(1 for p in store_points if p["name"])
    print(f"Retailers with a usable label: {named:,} of {len(store_points):,}")

    return {"tracts": {"type": "FeatureCollection", "features": features},
            "stores": store_points,
            "variables": present}


def population_weighted_poverty(tracts: pd.DataFrame) -> float | None:
    """The share of Harris County residents living below the poverty line,
    as a single county-wide figure.

    Computed as sum(pct_below_poverty * total_population) / sum(total_population)
    across all tracts with both values present. This is weighted by tract
    population on purpose: a plain average of the tract percentages would
    give a 900-person tract the same influence as an 8,000-person one, which
    is not the county rate and is a common way this number goes wrong.
    """
    usable = tracts.dropna(subset=["pct_below_poverty", "total_population"])
    total = usable["total_population"].sum()
    if not total:
        return None
    weighted = (usable["pct_below_poverty"] * usable["total_population"]).sum()
    return float(weighted / total)


def build_report() -> Report:
    """Assemble the report's object tree: a row of summary metrics, then the
    interactive map."""
    store_cols = discover_store_columns()
    tracts = get_tracts()
    all_stores = get_stores(store_cols)
    stores, closed_count = filter_open_stores(all_stores)

    print(f"Loaded {len(tracts):,} tracts and {len(stores):,} in-county retailers.")

    map_data = build_map_data(tracts, stores)

    tract_count = len(map_data["tracts"]["features"])
    population = tracts["total_population"].sum(skipna=True)
    poverty_rate = population_weighted_poverty(tracts)
    tracts_with_store = len({s for s in stores["tract_geoid"]})
    tracts_without = tract_count - tracts_with_store

    metrics = TextSection(
        data=None,
        title=f"{COUNTY_LABEL} at a glance",
        children=[
            MetricCard(data=f"{tract_count:,}", label="Census tracts mapped"),
            MetricCard(
                data=f"{int(population):,}" if pd.notna(population) else "No data",
                label="Total population",
                note="2020-2024 ACS five-year estimates",
            ),
            MetricCard(
                data=f"{poverty_rate:.1f}%" if poverty_rate is not None else "No data",
                label="Below poverty",
                note="Weighted by tract population",
            ),
            MetricCard(
                data=f"{len(map_data['stores']):,}",
                label="SNAP retailers",
                note=(
                    f"Currently authorized. {closed_count:,} closed "
                    "retailer(s) excluded."
                    if OPEN_STORES_ONLY
                    else f"All retailers on file, including {closed_count:,} closed."
                ),
            ),
            MetricCard(
                data=f"{tracts_without:,}",
                label="Tracts with no SNAP retailer",
                note=f"of {tract_count:,} tracts",
            ),
        ],
    )

    map_section = MapSection(
        data=map_data,
        title="Demographics and SNAP retailer locations",
        body=(
            "Pick a measure to shade the tracts. Only one is shown at a time, "
            "because the measures use different units and two colour scales on "
            "the same polygons cannot be read together. Amber dots are "
            "SNAP-authorized retailers. Click any tract for its values."
        ),
    )

    return Report(
        children=[metrics, map_section],
        report_title=REPORT_NAME,
        report_subtitle=(
            f"{COUNTY_LABEL} - 2020-2024 American Community Survey tract profile "
            "with SNAP-authorized retailer locations"
        ),
        footer_text=(
            "Sources: US Census Bureau American Community Survey 2020-2024 "
            "five-year estimates; Census TIGER/Line 2024 tract boundaries; "
            "USDA SNAP Retailer Locator. Tract boundaries are simplified for "
            "display. ACS figures describe tracts, not individuals."
        ),
    )


def main() -> None:
    report = build_report()
    html = report.render()
    publish_report(
        html,
        report_name=REPORT_NAME,
        report_desc=REPORT_DESCRIPTION,
        local_filename=str(REPORT_DIR / OUTPUT_FILENAME),
    )


if __name__ == "__main__":
    main()