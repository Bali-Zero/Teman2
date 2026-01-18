```typescript
import { render } from '@testing-library/react';
import globalError from './global-error';

// Mocking external dependencies
vi.mock('react', () => ({
  ...vi.originalMock,
  useState: vi.fn(),
}));

describe('GlobalError', () => {
  beforeEach(() => {
    (useState as jest.Mock).mockReturnValue([null, {}]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('should render correctly with no error', () => {
    const { container } = render(<globalError />);
    expect(container.firstChild).toBeNull();
  });

  it('should display error message when error is present', () => {
    (useState as jest.Mock).mockReturnValue([new Error('Test Error'), {}]);
    const { getByText } = render(<globalError />);
    expect(getByText('Test Error')).toBeInTheDocument();
  });

  it('should handle user interaction with dismiss button', async () => {
    (useState as jest.Mock).mockReturnValue([new Error('Test Error'), {}]);
    const { getByRole, rerender } = render(<globalError />);
    
    await userEvent.click(screen.getByRole('button'));
    
    expect(getByRole('alert')).toHaveTextContent('');
  });

  it('should not display error message when no error is present', () => {
    (useState as jest.Mock).mockReturnValue([null, {}]);
    const { queryByText } = render(<globalError />);
    expect(queryByText(/error/i)).toBeNull();
  });
});
```;
