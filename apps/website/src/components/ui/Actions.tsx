import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ReactNode,
} from "react";
import styles from "../../styles/design-system.module.css";
import { classNames } from "./classNames";

export type ActionVariant = "primary" | "secondary" | "copper";

const variantClass: Record<ActionVariant, string> = {
  primary: styles.buttonPrimary,
  secondary: styles.buttonSecondary,
  copper: styles.buttonCopper,
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: ActionVariant;
};

export function Button({
  children,
  className,
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={classNames(
        styles.theme,
        styles.button,
        variantClass[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export type ButtonLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  children: ReactNode;
  href: string;
  variant?: ActionVariant;
};

export function ButtonLink({
  children,
  className,
  variant = "primary",
  ...props
}: ButtonLinkProps) {
  return (
    <a
      className={classNames(
        styles.theme,
        styles.button,
        variantClass[variant],
        className,
      )}
      {...props}
    >
      {children}
    </a>
  );
}

export type TextLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  children: ReactNode;
  href: string;
  tone?: "copper" | "ink";
};

export function TextLink({
  children,
  className,
  tone = "copper",
  ...props
}: TextLinkProps) {
  return (
    <a
      className={classNames(
        styles.theme,
        styles.textLink,
        tone === "ink" && styles.textLinkInk,
        className,
      )}
      {...props}
    >
      {children}
    </a>
  );
}
