/**
 * Authentic Maharashtra Geographic Data & SVG Geometry
 * Extracted directly from the original Maharashtra Policy Simulator prototype.
 *
 * Epistemic boundary:
 * Contains the 35 districts, geographic coordinate bounds, Voronoi bisector clipping,
 * and SVG boundary path for the state of Maharashtra.
 */

// Geographic outline coordinates of Maharashtra [lon, lat] from authentic prototype
export const MAHARASHTRA_OUTLINE = [
  [72.7, 20.1], [73.0, 20.6], [73.6, 20.9], [73.8, 21.4], [74.2, 21.9], [74.8, 21.8], [75.6, 21.6], [76.3, 21.4],
  [76.8, 21.65], [77.5, 21.75], [78.2, 21.7], [78.8, 21.55], [79.4, 21.65], [80.0, 21.75], [80.6, 21.45], [80.9, 21.1],
  [80.7, 20.6], [80.5, 20.0], [80.2, 19.7], [80.4, 19.2], [80.1, 18.8], [79.9, 18.4], [79.5, 18.9], [79.1, 19.3],
  [78.7, 19.5], [78.3, 19.7], [78.1, 19.5], [77.7, 19.5], [77.6, 19.1], [77.3, 18.8], [77.2, 18.4], [76.7, 18.2],
  [76.2, 18.0], [76.0, 17.6], [75.7, 17.3], [75.3, 17.2], [74.9, 17.0], [74.6, 16.6], [74.3, 16.1], [74.1, 15.8],
  [73.7, 15.75], [73.5, 16.1], [73.3, 16.8], [73.2, 17.5], [73.0, 18.2], [72.9, 18.8], [72.8, 19.4]
];

// Administrative regions of Maharashtra
export const ADMINISTRATIVE_REGIONS = {
  K: 'Konkan',
  W: 'Western Maharashtra',
  N: 'North Maharashtra',
  M: 'Marathwada',
  V: 'Vidarbha'
};

// All 35 Districts: [id, full_name, region_key, lon, lat, pin_side, optional_short_name]
export const MAHARASHTRA_DISTRICTS = [
  ['mumbai', 'Mumbai', 'K', 72.9, 19.06, 'l'],
  ['thane', 'Thane', 'K', 73.05, 19.25, 'r'],
  ['palghar', 'Palghar', 'K', 72.9, 19.7, 'l'],
  ['raigad', 'Raigad', 'K', 72.98, 18.6, 'l'],
  ['ratnagiri', 'Ratnagiri', 'K', 73.3, 16.99, 'l'],
  ['sindhudurg', 'Sindhudurg', 'K', 73.68, 16.12, 'l'],
  ['pune', 'Pune', 'W', 73.86, 18.52, 'r'],
  ['satara', 'Satara', 'W', 74.0, 17.69, 'r'],
  ['sangli', 'Sangli', 'W', 74.56, 16.85, 'r'],
  ['kolhapur', 'Kolhapur', 'W', 74.24, 16.7, 'l'],
  ['solapur', 'Solapur', 'W', 75.91, 17.66, 'r'],
  ['nashik', 'Nashik', 'N', 73.79, 20.0, 'l'],
  ['dhule', 'Dhule', 'N', 74.78, 20.9, 'l'],
  ['nandurbar', 'Nandurbar', 'N', 74.24, 21.37, 'r'],
  ['jalgaon', 'Jalgaon', 'N', 75.57, 21.0, 'r'],
  ['ahmednagar', 'Ahmednagar', 'N', 74.74, 19.09, 'b'],
  ['sambhajinagar', 'Chhatrapati Sambhajinagar', 'M', 75.34, 19.88, 'l', 'Chh. Sambhajinagar'],
  ['jalna', 'Jalna', 'M', 75.88, 19.84, 'r'],
  ['beed', 'Beed', 'M', 75.76, 18.99, 'r'],
  ['latur', 'Latur', 'M', 76.58, 18.4, 'r'],
  ['dharashiv', 'Dharashiv', 'M', 76.04, 18.18, 'l'],
  ['nanded', 'Nanded', 'M', 77.32, 19.15, 'r'],
  ['hingoli', 'Hingoli', 'M', 77.15, 19.72, 'r'],
  ['parbhani', 'Parbhani', 'M', 76.78, 19.27, 'l'],
  ['buldhana', 'Buldhana', 'V', 76.18, 20.53, 'l'],
  ['akola', 'Akola', 'V', 77.0, 20.7, 'r'],
  ['washim', 'Washim', 'V', 77.15, 20.1, 'l'],
  ['amravati', 'Amravati', 'V', 77.76, 20.93, 'r'],
  ['yavatmal', 'Yavatmal', 'V', 78.12, 20.39, 'r'],
  ['wardha', 'Wardha', 'V', 78.6, 20.74, 'r'],
  ['nagpur', 'Nagpur', 'V', 79.09, 21.15, 'l'],
  ['bhandara', 'Bhandara', 'V', 79.65, 21.17, 'r'],
  ['gondia', 'Gondia', 'V', 80.19, 21.46, 'r'],
  ['chandrapur', 'Chandrapur', 'V', 79.3, 19.96, 'r'],
  ['gadchiroli', 'Gadchiroli', 'V', 80.18, 20.18, 'r']
];

// SVG Geographic Projection Constants & Helpers from authentic prototype
export const MAP_WIDTH = 860;
export const MAP_HEIGHT = 650;
const S = 90;
const K = 0.945;
const OX = 30;
const OY = 24;

export const projectLon = (lon) => OX + (lon - 72.5) * K * S;
export const projectLat = (lat) => OY + (22.1 - lat) * S;

// Sutherland-Hodgman Polygon Clipping against half-plane A*x + B*y <= C
function clipPolygon(poly, A, B, C) {
  const out = [];
  for (let i = 0; i < poly.length; i++) {
    const p = poly[i];
    const q = poly[(i + 1) % poly.length];
    const dp = A * p[0] + B * p[1] - C;
    const dq = A * q[0] + B * q[1] - C;
    if (dp <= 0) out.push(p);
    if ((dp < 0 && dq > 0) || (dp > 0 && dq < 0)) {
      const t = dp / (dp - dq);
      out.push([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]);
    }
  }
  return out;
}

/**
 * Builds the authentic projected map geometry including:
 * - State outline SVG path (`outlineD`)
 * - Clipped Voronoi district polygon cells (`cities` with `d` attribute)
 */
export function buildMaharashtraMapGeometry() {
  const projectedOutline = MAHARASHTRA_OUTLINE.map(([lon, lat]) => [
    projectLon(lon),
    projectLat(lat)
  ]);

  const outlineD =
    projectedOutline
      .map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1))
      .join(' ') + ' Z';

  const cities = MAHARASHTRA_DISTRICTS.map((d) => ({
    id: d[0],
    name: d[1],
    shortName: d[6] || d[1],
    region: ADMINISTRATIVE_REGIONS[d[2]],
    regionKey: d[2],
    lon: d[3],
    lat: d[4],
    side: d[5],
    x: projectLon(d[3]),
    y: projectLat(d[4])
  }));

  // Compute Voronoi cells clipped to the Maharashtra boundary
  cities.forEach((c, i) => {
    let cell = projectedOutline.slice();
    for (let j = 0; j < cities.length && cell.length; j++) {
      if (j === i) continue;
      const o = cities[j];
      cell = clipPolygon(
        cell,
        2 * (o.x - c.x),
        2 * (o.y - c.y),
        o.x * o.x + o.y * o.y - c.x * c.x - c.y * c.y
      );
    }
    c.d = cell.length
      ? cell
          .map((p, n) => (n ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1))
          .join(' ') + ' Z'
      : '';
  });

  return { outlineD, cities };
}
