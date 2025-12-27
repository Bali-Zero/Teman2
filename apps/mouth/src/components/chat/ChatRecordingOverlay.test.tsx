import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatRecordingOverlay, ChatRecordingOverlayProps } from './ChatRecordingOverlay';

describe('ChatRecordingOverlay', () => {
  const defaultProps: ChatRecordingOverlayProps = {
    isRecording: false,
    recordingTime: 0,
  };

  describe('Visibility', () => {
    it('should not render when not recording', () => {
      const { container } = render(<ChatRecordingOverlay {...defaultProps} isRecording={false} />);
      expect(container.firstChild).toBeNull();
    });

    it('should render when recording', () => {
      render(<ChatRecordingOverlay {...defaultProps} isRecording={true} />);
      expect(screen.getByText('Release to send')).toBeInTheDocument();
    });
  });

  describe('Time formatting', () => {
    it('should display 0:00 at start', () => {
      render(<ChatRecordingOverlay isRecording={true} recordingTime={0} />);
      expect(screen.getByText('0:00')).toBeInTheDocument();
    });

    it('should display seconds correctly', () => {
      render(<ChatRecordingOverlay isRecording={true} recordingTime={5} />);
      expect(screen.getByText('0:05')).toBeInTheDocument();
    });

    it('should display minutes and seconds correctly', () => {
      render(<ChatRecordingOverlay isRecording={true} recordingTime={65} />);
      expect(screen.getByText('1:05')).toBeInTheDocument();
    });

    it('should pad seconds with leading zero', () => {
      render(<ChatRecordingOverlay isRecording={true} recordingTime={61} />);
      expect(screen.getByText('1:01')).toBeInTheDocument();
    });

    it('should display double-digit seconds without extra padding', () => {
      render(<ChatRecordingOverlay isRecording={true} recordingTime={30} />);
      expect(screen.getByText('0:30')).toBeInTheDocument();
    });
  });

  describe('UI elements', () => {
    it('should show pulsing indicator', () => {
      const { container } = render(<ChatRecordingOverlay isRecording={true} recordingTime={0} />);
      expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('should show red indicator dot', () => {
      const { container } = render(<ChatRecordingOverlay isRecording={true} recordingTime={0} />);
      expect(container.querySelector('.bg-red-500')).toBeInTheDocument();
    });

    it('should show instruction text', () => {
      render(<ChatRecordingOverlay isRecording={true} recordingTime={0} />);
      expect(screen.getByText('Release to send')).toBeInTheDocument();
    });
  });
});
