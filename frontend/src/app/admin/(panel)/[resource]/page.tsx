import { notFound } from "next/navigation";
import { isResourceName } from "@/components/admin/resource-names";
import { ListScreen } from "@/components/admin/screens";

export default async function ResourceListPage(props: PageProps<"/admin/[resource]">) {
  const { resource } = await props.params;
  if (!isResourceName(resource)) notFound();
  return <ListScreen name={resource} />;
}
