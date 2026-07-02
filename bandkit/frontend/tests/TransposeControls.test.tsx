import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TransposeControls } from '../src/components/TransposeControls'

test('chama onTranspose com +1 ao clicar em +', async () => {
  const onTranspose = vi.fn()
  render(<TransposeControls semitones={0} onTranspose={onTranspose} keyName='F' />)
  await userEvent.click(screen.getByRole('button', { name: '+' }))
  expect(onTranspose).toHaveBeenCalledWith(1)
})

test('chama onTranspose com -1 ao clicar em −', async () => {
  const onTranspose = vi.fn()
  render(<TransposeControls semitones={0} onTranspose={onTranspose} keyName='F' />)
  await userEvent.click(screen.getByRole('button', { name: '−' }))
  expect(onTranspose).toHaveBeenCalledWith(-1)
})

test('exibe o nome do tom atual', () => {
  render(<TransposeControls semitones={3} onTranspose={vi.fn()} keyName='G#m' />)
  expect(screen.getByText(/G#m/)).toBeInTheDocument()
})
