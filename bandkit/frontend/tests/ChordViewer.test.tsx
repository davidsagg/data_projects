import { render, screen } from '@testing-library/react'
import { ChordViewer } from '../src/components/ChordViewer'

const bkcp = '{title: Garota de Ipanema}\n{key: F}\n[Verso]\n[F]Olha que coisa'

test('renderiza o título da música', () => {
  render(<ChordViewer bkcp={bkcp} semitones={0} />)
  expect(screen.getByText(/Garota de Ipanema/i)).toBeInTheDocument()
})

test('renderiza acordes sem colchetes', () => {
  render(<ChordViewer bkcp={bkcp} semitones={0} />)
  expect(screen.getByText('F')).toBeInTheDocument()
})

test('transpõe acordes quando semitones muda', () => {
  const { rerender } = render(<ChordViewer bkcp={bkcp} semitones={0} />)
  rerender(<ChordViewer bkcp={bkcp} semitones={2} />)
  expect(screen.getByText('G')).toBeInTheDocument() // F+2=G
})
