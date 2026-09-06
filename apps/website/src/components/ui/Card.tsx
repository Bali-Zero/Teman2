import type { HTMLAttributes, ReactNode } from "react";
import styles from "../../styles/design-system.module.css";
import { classNames } from "./classNames";

type CardElement = "article" | "div";

export type CardProps = HTMLAttributes<HTMLElement> & {
  as?: CardElement;
  children: ReactNode;
  tone?: "paper" | "quiet";
};

export function Card({
  as: Element = "article",
  children,
  className,
  tone = "paper",
  ...props
}: CardProps) {
  return (
    <Element
      className={classNames(
        styles.theme,
        styles.card,
        tone === "quiet" ? styles.cardQuiet : styles.cardPaper,
        className,
      )}
      {...props}
    >
      {children}
    </Element>
  );
}
