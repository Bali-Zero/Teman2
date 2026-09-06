import {
  Button,
  ButtonLink,
  Card,
  Container,
  SectionHeading,
  TextLink,
} from ".";

export function DesignSystemFixture() {
  return (
    <Container
      aria-label="Design system fixture"
      as="main"
      data-testid="design-system-fixture"
      width="content"
    >
      <SectionHeading
        description="A focused set of server-compatible primitives for service and editorial routes."
        eyebrow="Bali Zero website"
        id="fixture-title"
        title="Clear decisions, on paper."
      />
      <Card aria-labelledby="fixture-card-title">
        <h3 id="fixture-card-title">A native, keyboard-ready action group</h3>
        <div>
          <Button type="button">Ask a question</Button>
          <ButtonLink href="#fixture-title" variant="secondary">
            Review the brief
          </ButtonLink>
          <TextLink href="#fixture-title">Read the evidence</TextLink>
        </div>
      </Card>
    </Container>
  );
}
