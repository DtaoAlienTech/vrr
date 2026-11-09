import { notFound } from "next/navigation";
import { PageEditor } from "@/components/admin/PagesScreens";

export default async function PageEditorPage(props: PageProps<"/admin/pages/[id]">) {
  const { id } = await props.params;
  if (!/^\d{1,12}$/.test(id)) notFound();
  return <PageEditor id={id} />;
}
