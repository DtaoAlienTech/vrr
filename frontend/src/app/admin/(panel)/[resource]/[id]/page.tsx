import { notFound } from "next/navigation";
import { isResourceName } from "@/components/admin/resource-names";
import { EditorScreen } from "@/components/admin/screens";

export default async function ResourceEditorPage(props: PageProps<"/admin/[resource]/[id]">) {
  const { resource, id } = await props.params;
  if (!isResourceName(resource) || !/^(new|\d{1,12})$/.test(id)) notFound();
  return <EditorScreen name={resource} id={id} />;
}
