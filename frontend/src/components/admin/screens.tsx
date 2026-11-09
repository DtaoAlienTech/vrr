"use client";

// Client screens that can be chosen by name from a server page (functions cannot cross over).
import { ResourceEditor, ResourceList } from "./ResourceScreens";
import { ACTIVITIES, COURSES, DEPARTMENTS, FACULTY, GALLERY, NEWS, type ResourceConfig } from "./resources";
import type { ResourceName } from "./resource-names";
import { MediaBrowser } from "./media";
import { Heading } from "./ui";

const CONFIGS: Record<ResourceName, ResourceConfig> = {
  news: NEWS,
  activities: ACTIVITIES,
  gallery: GALLERY,
  departments: DEPARTMENTS,
  courses: COURSES,
  faculty: FACULTY,
};

export function ListScreen({ name }: { name: ResourceName }) {
  return <ResourceList config={CONFIGS[name]} />;
}

export function EditorScreen({ name, id }: { name: ResourceName; id: string }) {
  return <ResourceEditor config={CONFIGS[name]} id={id} />;
}

export function MediaScreen() {
  return (
    <>
      <Heading title="Photos & files" sub="Everything you upload is kept here. Photos are resized automatically and camera location data is removed. Pick them from any form." />
      <MediaBrowser manage />
    </>
  );
}
