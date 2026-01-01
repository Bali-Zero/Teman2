'use client';

import React, { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

type AnimationType =
  | 'fade'
  | 'slide-up'
  | 'slide-down'
  | 'slide-left'
  | 'slide-right'
  | 'zoom-in'
  | 'zoom-out'
  | 'flip-up'
  | 'flip-down';

interface ScrollRevealProps {
  children: React.ReactNode;
  animation?: AnimationType;
  delay?: number;
  duration?: number;
  threshold?: number;
  once?: boolean;
  className?: string;
}

/**
 * ScrollReveal - Animate elements when they scroll into view
 *
 * Usage:
 * <ScrollReveal animation="slide-up" delay={100}>
 *   <div>Content here</div>
 * </ScrollReveal>
 */
export function ScrollReveal({
  children,
  animation = 'fade',
  delay = 0,
  duration = 500,
  threshold = 0.1,
  once = true,
  className,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (once) {
            observer.disconnect();
          }
        } else if (!once) {
          setIsVisible(false);
        }
      },
      {
        threshold,
        rootMargin: '0px 0px -50px 0px',
      }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [threshold, once]);

  const getAnimationStyles = (): React.CSSProperties => {
    const baseStyle: React.CSSProperties = {
      transition: `all ${duration}ms cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms`,
    };

    if (!isVisible) {
      switch (animation) {
        case 'fade':
          return { ...baseStyle, opacity: 0 };
        case 'slide-up':
          return { ...baseStyle, opacity: 0, transform: 'translateY(30px)' };
        case 'slide-down':
          return { ...baseStyle, opacity: 0, transform: 'translateY(-30px)' };
        case 'slide-left':
          return { ...baseStyle, opacity: 0, transform: 'translateX(30px)' };
        case 'slide-right':
          return { ...baseStyle, opacity: 0, transform: 'translateX(-30px)' };
        case 'zoom-in':
          return { ...baseStyle, opacity: 0, transform: 'scale(0.9)' };
        case 'zoom-out':
          return { ...baseStyle, opacity: 0, transform: 'scale(1.1)' };
        case 'flip-up':
          return { ...baseStyle, opacity: 0, transform: 'perspective(1000px) rotateX(10deg)' };
        case 'flip-down':
          return { ...baseStyle, opacity: 0, transform: 'perspective(1000px) rotateX(-10deg)' };
        default:
          return { ...baseStyle, opacity: 0 };
      }
    }

    return {
      ...baseStyle,
      opacity: 1,
      transform: 'translateY(0) translateX(0) scale(1) rotateX(0)',
    };
  };

  return (
    <div ref={ref} style={getAnimationStyles()} className={cn(className)}>
      {children}
    </div>
  );
}

/**
 * Staggered reveal for list items
 */
interface StaggeredRevealProps {
  children: React.ReactNode[];
  animation?: AnimationType;
  staggerDelay?: number;
  duration?: number;
  className?: string;
  itemClassName?: string;
}

export function StaggeredReveal({
  children,
  animation = 'slide-up',
  staggerDelay = 100,
  duration = 500,
  className,
  itemClassName,
}: StaggeredRevealProps) {
  return (
    <div className={className}>
      {React.Children.map(children, (child, index) => (
        <ScrollReveal
          key={index}
          animation={animation}
          delay={index * staggerDelay}
          duration={duration}
          className={itemClassName}
        >
          {child}
        </ScrollReveal>
      ))}
    </div>
  );
}

export default ScrollReveal;
