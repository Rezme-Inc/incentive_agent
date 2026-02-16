import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressIndicator } from '../../components/ProgressIndicator';

describe('ProgressIndicator', () => {
  it('should display current step and percentage', () => {
    render(
      <ProgressIndicator
        currentStep="cjars_categorization"
        percentage={45}
        stepsCompleted={['extraction', 'validation']}
        stepsRemaining={['jurisdiction_compliance', 'verification']}
      />
    );

    expect(screen.getByText(/Cjars Categorization/)).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('should display completed steps', () => {
    render(
      <ProgressIndicator
        currentStep="cjars_categorization"
        percentage={45}
        stepsCompleted={['extraction', 'validation']}
        stepsRemaining={['jurisdiction_compliance']}
      />
    );

    expect(screen.getByText('Extraction')).toBeInTheDocument();
    expect(screen.getByText('Validation')).toBeInTheDocument();
  });

  it('should display remaining steps', () => {
    render(
      <ProgressIndicator
        currentStep="cjars_categorization"
        percentage={45}
        stepsCompleted={['extraction']}
        stepsRemaining={['jurisdiction_compliance', 'verification']}
      />
    );

    expect(screen.getByText('Jurisdiction Compliance')).toBeInTheDocument();
    expect(screen.getByText('Verification')).toBeInTheDocument();
  });

  it('should format step names correctly', () => {
    render(
      <ProgressIndicator
        currentStep="jurisdiction_compliance"
        percentage={75}
        stepsCompleted={['extraction', 'cjars_categorization']}
        stepsRemaining={['verification']}
      />
    );

    expect(screen.getByText(/Jurisdiction Compliance/)).toBeInTheDocument();
  });

  it('should show progress bar with correct width', () => {
    const { container } = render(
      <ProgressIndicator
        currentStep="test_step"
        percentage={60}
        stepsCompleted={[]}
        stepsRemaining={[]}
      />
    );

    const progressBar = container.querySelector('.bg-blue-600');
    expect(progressBar).toHaveStyle({ width: '60%' });
  });

  it('should display processing indicator', () => {
    render(
      <ProgressIndicator
        currentStep="test_step"
        percentage={30}
        stepsCompleted={[]}
        stepsRemaining={[]}
      />
    );

    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });
});
