import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { contactsApi } from '../api/client'
import type { ContactListItem } from '../types'
import { BulkGeocodeButton } from '../components/BulkGeocodeButton'
import { Card } from '../components/Card'

interface CityGroup {
  city: string
  latitude: number
  longitude: number
  contacts: ContactListItem[]
}

export function MapPage() {
  const [contacts, setContacts] = useState<ContactListItem[]>([])
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    contactsApi.list({ page_size: 5000 }).then((res) => {
      setContacts(res.items)
      setLoading(false)
    })
  }

  useEffect(load, [])

  const cityGroups = useMemo<CityGroup[]>(() => {
    const map = new Map<string, CityGroup>()
    for (const c of contacts) {
      if (c.latitude == null || c.longitude == null || !c.city) continue
      const key = c.city
      if (!map.has(key)) {
        map.set(key, { city: c.city, latitude: c.latitude, longitude: c.longitude, contacts: [] })
      }
      map.get(key)!.contacts.push(c)
    }
    return [...map.values()]
  }, [contacts])

  const geocodedCount = cityGroups.reduce((sum, g) => sum + g.contacts.length, 0)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border bg-surface px-8 py-4">
        <div>
          <h1 className="text-xl font-semibold text-text">Mapa de contatos</h1>
          <p className="text-sm text-muted">
            {loading ? 'Carregando...' : `${geocodedCount} de ${contacts.length} contatos com cidade definida`}
          </p>
        </div>
        <BulkGeocodeButton onDone={load} />
      </div>

      {!loading && cityGroups.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-8">
          <Card className="max-w-md text-center">
            <p className="mb-3 text-sm text-muted">
              Nenhum contato tem cidade e coordenadas ainda. Preencha a cidade manualmente no perfil de um
              contato, ou use o botão acima para sugerir cidades a partir da empresa.
            </p>
            <Link to="/contacts" className="text-sm font-medium text-accent hover:underline">
              Ir para a lista de contatos
            </Link>
          </Card>
        </div>
      ) : (
        <div className="flex-1">
          <MapContainer center={[-14.235, -51.925]} zoom={3} className="h-full w-full">
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            />
            {cityGroups.map((g) => (
              <CircleMarker
                key={g.city}
                center={[g.latitude, g.longitude]}
                radius={Math.min(28, 8 + Math.sqrt(g.contacts.length) * 4)}
                pathOptions={{ color: '#6d4aff', fillColor: '#6d4aff', fillOpacity: 0.5, weight: 2 }}
              >
                <Popup maxHeight={200}>
                  <div className="min-w-40">
                    <p className="mb-1 font-semibold">
                      {g.city} ({g.contacts.length})
                    </p>
                    <ul className="max-h-32 space-y-1 overflow-y-auto text-sm">
                      {g.contacts.slice(0, 20).map((c) => (
                        <li key={c.id}>
                          <a href={`/contacts/${c.id}`} className="text-accent hover:underline">
                            {c.first_name} {c.last_name}
                          </a>
                          {c.company && <span className="text-muted"> · {c.company}</span>}
                        </li>
                      ))}
                      {g.contacts.length > 20 && (
                        <li className="text-muted">e mais {g.contacts.length - 20}...</li>
                      )}
                    </ul>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
      )}
    </div>
  )
}
