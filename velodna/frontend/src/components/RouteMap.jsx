import "leaflet/dist/leaflet.css"
import { useEffect, useRef } from "react"
import { MapContainer, TileLayer, Polyline, useMap } from "react-leaflet"

function FitBounds({ positions }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length > 1) {
      map.fitBounds(positions, { padding: [20, 20] })
    }
  }, [positions, map])
  return null
}

export default function RouteMap({ waypoints = [], activityDate }) {
  if (!waypoints || waypoints.length === 0) {
    return (
      <div style={styles.card}>
        <h2 style={styles.title}>Rota</h2>
        <p style={styles.muted}>Selecione uma atividade com GPS para ver o trajeto.</p>
      </div>
    )
  }

  const positions = waypoints.map((w) => [w.lat, w.lon])
  const center = positions[Math.floor(positions.length / 2)]

  return (
    <div style={styles.card}>
      <div style={styles.titleRow}>
        <h2 style={styles.title}>Rota</h2>
        {activityDate && <span style={styles.sub}>{activityDate}</span>}
        <span style={styles.pts}>{positions.length} pontos GPS</span>
      </div>
      <div style={styles.mapWrapper}>
        <MapContainer
          center={center}
          zoom={13}
          style={{ height: "100%", width: "100%", borderRadius: 8 }}
          scrollWheelZoom={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Polyline positions={positions} color="#3b82f6" weight={3} opacity={0.85} />
          <FitBounds positions={positions} />
        </MapContainer>
      </div>
    </div>
  )
}

const styles = {
  card: {
    background: "#1e293b",
    borderRadius: 12,
    padding: 24,
    boxShadow: "0 2px 12px rgba(0,0,0,0.4)",
  },
  titleRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  title: { margin: 0, fontSize: 18, fontWeight: 600, color: "#f1f5f9" },
  sub: { fontSize: 13, color: "#64748b" },
  pts: {
    marginLeft: "auto",
    fontSize: 12,
    color: "#475569",
    background: "#0f172a",
    padding: "2px 8px",
    borderRadius: 10,
  },
  muted: { color: "#94a3b8" },
  mapWrapper: {
    height: 340,
    borderRadius: 8,
    overflow: "hidden",
  },
}
