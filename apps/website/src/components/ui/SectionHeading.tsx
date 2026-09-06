import type { HTMLAttributes, ReactNode } from "react";
import styles from "../../styles/design-system.module.css";
import { classNames } from "./classNames";

export type SectionHeadingProps = Omit<
  HTMLAttributes<HTMLElement>,
  "title"
> & {
  align?: "start" | "split";
  description?: ReactNode;
  eyebrow?: ReactNode;
  id?: string;
  level?: 2 | 3;
  title: ReactNode;
};

export function SectionHeading({
  align = "start",
  className,
  description,
  eyebrow,
  id,
  level = 2,
  title,
  ...props
}: SectionHeadingProps) {
  const Heading = level === 3 ? "h3" : "h2";

  return (
    <header
      className={classNames(
        styles.theme,
        styles.sectionHeading,
        align === "split" && styles.sectionHeadingSplit,
        className,
      )}
      {...props}
    >
      {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
      <Heading className={styles.headingTitle} id={id}>
        {title}
      </Heading>
      {description ? (
        <p className={styles.headingDescription}>{description}</p>
      ) : null}
    </header>
  );
}
