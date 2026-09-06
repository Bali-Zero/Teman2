import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ServiceDetail } from "../../../components/services/ServiceJourneys";
import { getServicePage, servicePages } from "../../../content/service-pages";

type ServiceRouteProps = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return servicePages.map(({ slug }) => ({ slug }));
}

export async function generateMetadata({
  params,
}: ServiceRouteProps): Promise<Metadata> {
  const service = getServicePage((await params).slug);
  return service
    ? {
        title: `${service.title} | Bali Zero`,
        description: service.metaDescription,
      }
    : { title: "Service not found | Bali Zero" };
}

export default async function ServiceRoute({ params }: ServiceRouteProps) {
  const service = getServicePage((await params).slug);
  if (!service) notFound();
  return <ServiceDetail service={service} />;
}
