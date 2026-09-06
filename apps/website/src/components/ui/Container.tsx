import type { HTMLAttributes, ReactNode } from "react";
import styles from "../../styles/design-system.module.css";
import { classNames } from "./classNames";

type ContainerElement = "div" | "section" | "main";

export type ContainerProps = HTMLAttributes<HTMLElement> & {
  as?: ContainerElement;
  children: ReactNode;
  width?: "content" | "wide";
};

export function Container({
  as: Element = "div",
  children,
  className,
  width = "wide",
  ...props
}: ContainerProps) {
  return (
    <Element
      className={classNames(
        styles.theme,
        styles.container,
        width === "content" ? styles.containerContent : styles.containerWide,
        className,
      )}
      {...props}
    >
      {children}
    </Element>
  );
}
