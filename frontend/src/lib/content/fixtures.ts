// DEVELOPMENT DATA ONLY. It mirrors the approved design so every page can be built and tested.
// Phase 1 adds the real database and API; then only api.ts changes and this file is deleted.
// Anything marked "Sample" is a placeholder that must never go live.
import type {
  Activity,
  Course,
  FacultyMember,
  GalleryItem,
  MediaRef,
  NewsItem,
  PageData,
  PageKey,
  RichDoc,
  RichNode,
  SiteSettings,
} from "./types";

const photo = (file: string, alt: string, width = 1156, height = 868, cropBottom = false): MediaRef => ({
  url: `/seed/photos/${file}`,
  alt,
  width,
  height,
  ...(cropBottom ? { cropBottom } : {}),
});
// The NSS photos are 1280x588 phone photos with a camera date stamp on the bottom edge.
const nssPhoto = (n: number, alt: string) => photo(`nss-${n}.jpg`, alt, 1280, 588, true);

// Small helpers to write rich text documents.
const p = (text: string): RichNode => ({ type: "paragraph", content: [{ type: "text", text }] });
const h = (text: string): RichNode => ({ type: "heading", attrs: { level: 2 }, content: [{ type: "text", text }] });
const ul = (...items: string[]): RichNode => ({
  type: "bulletList",
  content: items.map((item) => ({ type: "listItem", content: [p(item)] })),
});
const doc = (...content: RichNode[]): RichDoc => ({ type: "doc", content });

export const settings: SiteSettings = {
  name: "VRR Degree College",
  shortName: "VRR",
  tagline: "Kallur · Est. 2016",
  established: 2016,
  topBar: "Affiliated to Sri Venkateswara University · UGC",
  logo: { url: "/logo/vrr-mark.svg", alt: "VRR Degree College logo", width: 240, height: 280 },
  contact: { address: "Piler Road, Kallur", phone: "", whatsapp: "", email: "", hours: "", mapLink: "", mapEmbedUrl: "" },
  social: [],
  menu: [
    { label: "Home", href: "/" },
    { label: "About", href: "/about" },
    { label: "Courses", href: "/courses" },
    { label: "Faculty", href: "/faculty" },
    { label: "Admissions", href: "/admissions" },
    { label: "Activities", href: "/activities" },
    { label: "Gallery", href: "/gallery" },
    { label: "News", href: "/news" },
    { label: "Contact", href: "/contact" },
  ],
  footerCourses: [
    { label: "B.Sc Computer Science", href: "/courses/bsc-computer-science" },
    { label: "B.Sc Zoology", href: "/courses/bsc-zoology" },
    { label: "B.Com Computer Science", href: "/courses/bcom-computer-science" },
  ],
  affiliationText: "Affiliated to Sri Venkateswara University.",
  copyright: "© 2026 VRR Degree College. All rights reserved.",
  seo: {
    defaultTitle: "VRR Degree College, Kallur",
    titleTemplate: "%s | VRR Degree College",
    description:
      "VRR Degree College, Piler Road, Kallur. B.Sc Computer Science, B.Sc Zoology and B.Com programs affiliated to Sri Venkateswara University.",
    ogImage: photo("campus-1.jpg", "VRR Degree College building with the college bus"),
  },
};

export const courses: Course[] = [
  {
    slug: "bsc-computer-science",
    tab: "Computer Science",
    name: "B.Sc Computer Science",
    department: "Department of Computer Science",
    duration: "3 years",
    affiliation: "Sri Venkateswara University",
    summary: "Programming, databases and the foundations of modern computing, taught with hands-on lab work.",
    description: doc(
      p("Sample text: This program introduces students to programming, databases, networks and the foundations of computing."),
      p("The course description is written by the college and can be edited from the admin panel."),
    ),
    subjects: ["Programming fundamentals", "Data structures and databases", "Web technologies", "Mathematics for computing"],
  },
  {
    slug: "bsc-zoology",
    tab: "Zoology",
    name: "B.Sc Zoology",
    department: "Department of Zoology",
    duration: "3 years",
    affiliation: "Sri Venkateswara University",
    summary: "The study of animal life and ecology, with practical laboratory and field learning.",
  },
  {
    slug: "bcom-computer-science",
    tab: "Commerce",
    name: "B.Com Computer Science",
    department: "Department of Commerce",
    duration: "3 years",
    affiliation: "Sri Venkateswara University",
    summary: "Accounting and commerce fundamentals combined with practical computer skills.",
  },
];

export const activities: Activity[] = [
  {
    slug: "nss-campus-clean-up",
    group: "NSS",
    groupKey: "nss",
    year: "2022",
    title: "NSS volunteers: campus clean-up",
    summary: "Volunteers of the college National Service Scheme unit during a clean-up activity.",
    cover: nssPhoto(1, "NSS volunteers with the unit banner"),
    photos: [
      { media: nssPhoto(1, "NSS volunteers with the unit banner") },
      { media: nssPhoto(3, "Volunteers carrying a cleared shrub") },
      { media: nssPhoto(4, "Volunteers dragging cleared branches") },
      { media: nssPhoto(5, "NSS volunteer team") },
      { media: nssPhoto(2, "NSS volunteers with the banner") },
      { media: nssPhoto(6, "Volunteers clearing the field") },
      { media: nssPhoto(7, "NSS volunteers and the banner") },
    ],
  },
  {
    slug: "leo-club",
    group: "Leo Club",
    groupKey: "leo",
    title: "Leo Club of V.R.R. College, Kallur",
    summary: "Members of the Leo Club (Lions District 317E) with the club banner, taking part in a community activity.",
    cover: photo("leo-1.jpg", "Leo Club members with the club banner", 1400, 934),
    photos: [{ media: photo("leo-1.jpg", "Leo Club members with the club banner", 1400, 934) }],
  },
];

export const news: NewsItem[] = [
  {
    slug: "sample-admissions-open",
    title: "Sample: Admissions open for the new academic year",
    category: "Admission",
    publishedAt: "2026-10-28",
    summary: "Sample text. The college writes the notice and attaches any PDF from the admin panel.",
    body: doc(p("Sample text. The college writes the notice here and can attach a PDF.")),
    pinned: true,
    attachments: [],
  },
  {
    slug: "sample-semester-timetable",
    title: "Sample: Semester timetable released",
    category: "Notice",
    publishedAt: "2026-10-20",
    summary: "Sample text for a regular notice with a short summary.",
    body: doc(p("Sample text for a regular notice.")),
    attachments: [],
  },
  {
    slug: "sample-annual-day",
    title: "Sample: Annual day celebrations",
    category: "Event",
    publishedAt: "2026-10-12",
    summary: "Sample text for an event announcement with photos in the gallery.",
    body: doc(p("Sample text for an event announcement.")),
    attachments: [],
  },
  {
    slug: "sample-scholarship-information",
    title: "Sample: Scholarship information",
    category: "Notice",
    publishedAt: "2026-10-05",
    summary: "Sample text for scholarship and fee related information.",
    body: doc(p("Sample text for scholarship information.")),
    attachments: [],
  },
  {
    slug: "sample-leo-club-update",
    title: "Sample: Leo Club activity update",
    category: "Leo Club",
    publishedAt: "2026-10-02",
    summary: "Sample text. Photos of club activities are added to the gallery and shown on the home page.",
    body: doc(p("Sample text for a club activity update.")),
    attachments: [],
  },
];

const dept = (key: "cs" | "zoo" | "com") =>
  ({
    cs: { department: "Computer Science", departmentKey: "cs" },
    zoo: { department: "Zoology", departmentKey: "zoo" },
    com: { department: "Commerce", departmentKey: "com" },
  })[key];
export const faculty: FacultyMember[] = (["cs", "cs", "zoo", "zoo", "com", "com", "cs", "com"] as const).map(
  (key, index) => ({
    id: index + 1,
    name: `Sample Faculty ${index + 1}`,
    designation: "Designation (sample)",
    qualification: "Qualification (sample)",
    ...dept(key),
  }),
);

const g = (id: number, file: string, alt: string, caption: string, category: string, label: string, w = 1156, h = 868, crop = false): GalleryItem => ({
  id,
  media: photo(file, alt, w, h, crop),
  caption,
  category,
  categoryLabel: label,
});
export const gallery: GalleryItem[] = [
  g(1, "campus-2.jpg", "VRR Degree College building, front view", "Campus building", "campus", "Campus"),
  g(2, "campus-4.jpg", "Corner view of the college building", "Corner view", "campus", "Campus"),
  g(3, "campus-5.jpg", "Side view of the college building", "Side view", "campus", "Campus"),
  g(4, "campus-3.jpg", "Front view of the college building", "Front view", "campus", "Campus"),
  g(5, "campus-1.jpg", "The college bus in front of the building", "College bus", "campus", "Campus"),
  g(6, "leo-1.jpg", "Leo Club members with the club banner", "Leo Club volunteers", "leo", "Leo Club", 1400, 934),
  g(7, "nss-1.jpg", "NSS volunteers with the unit banner", "NSS volunteers", "nss", "NSS", 1280, 588, true),
  g(8, "nss-3.jpg", "Volunteers carrying a cleared shrub", "NSS clean-up", "nss", "NSS", 1280, 588, true),
  g(9, "nss-4.jpg", "Volunteers dragging cleared branches", "NSS clean-up", "nss", "NSS", 1280, 588, true),
  g(10, "nss-5.jpg", "NSS volunteer team", "NSS team", "nss", "NSS", 1280, 588, true),
  g(11, "nss-2.jpg", "NSS volunteers with the banner", "NSS volunteers", "nss", "NSS", 1280, 588, true),
  g(12, "nss-6.jpg", "Volunteers clearing the field", "NSS clean-up", "nss", "NSS", 1280, 588, true),
  g(13, "nss-7.jpg", "NSS volunteers and the banner", "NSS volunteers", "nss", "NSS", 1280, 588, true),
];

const seoDescription = (text: string) => text;

export const pages: Record<PageKey, PageData> = {
  home: {
    key: "home",
    slug: "",
    title: "Home",
    seo: {
      title: "VRR Degree College, Kallur | B.Sc and B.Com Degree College",
      description: settings.seo.description,
      ogImage: settings.seo.ogImage,
    },
    sections: [
      {
        id: 1,
        type: "hero",
        data: {
          label: "Kallur · Piler Road · Est. 2016",
          headline: "Shape your future at",
          highlight: "VRR Degree College",
          text: "Three-year undergraduate programs in Computer Science, Zoology and Commerce, affiliated to Sri Venkateswara University.",
          primaryCta: { label: "Enquire now", href: "/admissions#enquire" },
          secondaryCta: { label: "View courses", href: "/courses" },
          image: photo("campus-1.jpg", "VRR Degree College building with the college bus"),
        },
      },
      {
        id: 2,
        type: "stats",
        data: {
          items: [
            { value: "2016", label: "Established" },
            { value: "3", label: "Programs" },
            { value: "3", label: "Departments" },
            { value: "SVU", label: "Affiliated" },
          ],
        },
      },
      {
        id: 3,
        type: "notice_strip",
        data: {
          label: "Notices",
          items: [
            "Sample notice: Admissions open for the new academic year",
            "Sample notice: Semester timetable released",
            "Sample notice: Scholarship information",
          ],
        },
      },
      {
        id: 4,
        type: "collection_list",
        data: {
          collection: "courses",
          layout: "cards",
          heading: "Programs built for your next step",
          intro: "Choose from three undergraduate programs, each three years long.",
        },
      },
      {
        id: 5,
        type: "collection_list",
        data: {
          collection: "activities",
          layout: "cards",
          tone: "alt",
          heading: "Student activities: Leo Club & NSS",
          intro:
            "Service and leadership activities by our students. Photos and updates are added by the college from the admin panel.",
          cta: { label: "View all activities", href: "/activities" },
        },
      },
      {
        id: 6,
        type: "quote",
        data: {
          heading: "A word of welcome",
          text: "A short welcome message from the Principal will appear here. It can be changed any time from the admin panel, without a developer.",
          name: "Principal’s Name",
          role: "Principal, VRR Degree College",
        },
      },
      {
        id: 7,
        type: "card_grid",
        data: {
          variant: "numbered",
          tone: "alt",
          heading: "What students can expect",
          cards: [
            { title: "University affiliated", text: "Degrees under Sri Venkateswara University." },
            { title: "Three focused departments", text: "Computer Science, Zoology and Commerce." },
            { title: "Practical learning", text: "Lab work alongside classroom teaching. (Sample text)" },
            { title: "Supportive campus", text: "Guidance and care for every student. (Sample text)" },
          ],
        },
      },
      {
        id: 8,
        type: "media_gallery",
        data: {
          heading: "A look around the college",
          intro: "Photos and videos are added by the college from the admin panel.",
          cta: { label: "Open gallery", href: "/gallery" },
          items: gallery.slice(0, 5).map((item) => ({ media: item.media, caption: item.caption })),
        },
      },
      {
        id: 9,
        type: "enquiry_cta",
        data: {
          heading: "Ready to join? Send us your details.",
          text: "Our team will call you back with course details and the admission process.",
        },
      },
    ],
  },

  about: {
    key: "about",
    slug: "about",
    title: "About",
    seo: {
      title: "About VRR Degree College, Kallur",
      description: seoDescription("History, vision, mission and approvals of VRR Degree College, Kallur."),
    },
    sections: [
      {
        id: 1,
        type: "page_header",
        data: {
          title: "About the college",
          subtitle: "Founded in 2016 on Piler Road, Kallur, and affiliated to Sri Venkateswara University.",
        },
      },
      {
        id: 2,
        type: "two_column",
        data: {
          heading: "A college rooted in Kallur",
          main: [
            {
              id: 1,
              type: "timeline",
              data: {
                items: [
                  { label: "2016", text: "VRR Degree College was established at Piler Road, Kallur." },
                  { label: "Today", text: "Three departments and three undergraduate programs. (More milestones will be added by the college.)" },
                ],
              },
            },
            {
              id: 2,
              type: "rich_text",
              data: {
                body: doc(p("The college history will be written here in the college’s own words. The text can be edited from the admin panel at any time.")),
              },
            },
          ],
          aside: [
            { id: 3, type: "image", data: { media: photo("campus-3.jpg", "VRR Degree College front view") } },
            {
              id: 4,
              type: "panel",
              data: {
                items: [
                  { heading: "Vision", text: "Sample: To be a trusted centre of learning for the region." },
                  { heading: "Mission", text: "Sample: To give every student a strong foundation in knowledge and character." },
                ],
              },
            },
          ],
        },
      },
      {
        id: 3,
        type: "doc_list",
        data: {
          tone: "alt",
          heading: "Recognised and affiliated",
          docs: [
            { title: "Sri Venkateswara University", note: "Affiliation" },
            { title: "UGC", note: "Approval" },
          ],
        },
      },
      {
        id: 4,
        type: "card_grid",
        data: {
          variant: "tiles",
          heading: "Spaces for learning",
          intro: "Sample list. The college will confirm which facilities to show.",
          cards: [{ title: "Classrooms" }, { title: "Computer lab" }, { title: "Zoology lab" }, { title: "Library" }],
        },
      },
      {
        id: 5,
        type: "quote",
        data: {
          heading: "Leadership",
          text: "Message from the Chairman or Principal. (Sample placeholder)",
          name: "Name",
          role: "Designation",
        },
      },
    ],
  },

  courses: {
    key: "courses",
    slug: "courses",
    title: "Courses",
    seo: {
      title: "Courses",
      description: seoDescription("B.Sc Computer Science, B.Sc Zoology and B.Com Computer Science at VRR Degree College, Kallur."),
    },
    sections: [
      {
        id: 1,
        type: "page_header",
        data: { title: "Our courses", subtitle: "Three-year undergraduate programs, affiliated to Sri Venkateswara University." },
      },
      { id: 2, type: "collection_list", data: { collection: "courses", layout: "detailed" } },
    ],
  },

  faculty: {
    key: "faculty",
    slug: "faculty",
    title: "Faculty",
    seo: { title: "Faculty", description: seoDescription("Meet the faculty of VRR Degree College, Kallur.") },
    sections: [
      { id: 1, type: "page_header", data: { title: "Our faculty", subtitle: "Teachers and mentors across our three departments." } },
      { id: 2, type: "collection_list", data: { collection: "faculty", layout: "grid" } },
    ],
  },

  admissions: {
    key: "admissions",
    slug: "admissions",
    title: "Admissions",
    seo: {
      title: "Admissions",
      description: seoDescription("Admission process, eligibility and enquiry form for VRR Degree College, Kallur."),
    },
    sections: [
      { id: 1, type: "page_header", data: { title: "Admissions", subtitle: "How to join VRR Degree College." } },
      {
        id: 2,
        type: "card_grid",
        data: {
          variant: "steps",
          heading: "Four simple steps",
          intro: "Sample steps. The college will confirm the real admission process.",
          cards: [
            { title: "Enquire", text: "Send us your details or call the college office." },
            { title: "Choose a course", text: "Pick the program that fits your interest." },
            { title: "Submit documents", text: "Bring your certificates for verification." },
            { title: "Confirm", text: "Complete the formalities and join." },
          ],
        },
      },
      {
        id: 3,
        type: "two_column",
        data: {
          tone: "alt",
          heading: "Eligibility, dates and FAQs",
          main: [
            {
              id: 1,
              type: "key_value",
              data: {
                rows: [
                  { label: "Eligibility", value: "To be provided by the college" },
                  { label: "Application opens", value: "To be announced" },
                  { label: "Last date", value: "To be announced" },
                ],
              },
            },
            {
              id: 2,
              type: "faq",
              data: {
                items: [
                  { question: "Which documents do I need?", answer: "Sample answer. The college will list the required documents here." },
                  { question: "Can I visit the campus first?", answer: "Sample answer. Yes, visitors are welcome during office hours." },
                  { question: "Are scholarships available?", answer: "Sample answer. Details will be added by the college." },
                ],
              },
            },
          ],
          aside: [{ id: 3, type: "enquiry_form", data: { title: "Enquire now" } }],
        },
      },
    ],
  },

  activities: {
    key: "activities",
    slug: "activities",
    title: "Activities",
    seo: {
      title: "Student activities",
      description: seoDescription("Leo Club and NSS activities of VRR Degree College, Kallur."),
    },
    sections: [
      {
        id: 1,
        type: "page_header",
        data: { title: "Student activities", subtitle: "Leo Club and NSS activities by the students of VRR Degree College." },
      },
      { id: 2, type: "collection_list", data: { collection: "activities", layout: "albums" } },
    ],
  },

  gallery: {
    key: "gallery",
    slug: "gallery",
    title: "Gallery",
    seo: { title: "Gallery", description: seoDescription("Photos from VRR Degree College, Kallur.") },
    sections: [
      { id: 1, type: "page_header", data: { title: "Gallery", subtitle: "Campus life in photos." } },
      { id: 2, type: "collection_list", data: { collection: "gallery", layout: "mosaic", heading: "Around the campus" } },
    ],
  },

  news: {
    key: "news",
    slug: "news",
    title: "News",
    seo: {
      title: "News and notices",
      description: seoDescription("Latest news, notices and circulars from VRR Degree College, Kallur."),
    },
    sections: [
      { id: 1, type: "page_header", data: { title: "News & notices", subtitle: "Circulars, events and announcements." } },
      {
        id: 2,
        type: "two_column",
        data: {
          main: [{ id: 1, type: "collection_list", data: { collection: "news", layout: "list" } }],
          aside: [
            { id: 2, type: "panel", data: { title: "Categories", list: ["Admission", "Notice", "Event", "Exam", "Leo Club & activities"] } },
          ],
        },
      },
    ],
  },

  contact: {
    key: "contact",
    slug: "contact",
    title: "Contact",
    seo: {
      title: "Contact",
      description: seoDescription("Address, phone and enquiry form for VRR Degree College, Piler Road, Kallur."),
    },
    sections: [
      { id: 1, type: "page_header", data: { title: "Contact us", subtitle: "We would be happy to hear from you." } },
      {
        id: 2,
        type: "two_column",
        data: {
          main: [
            { id: 1, type: "contact_info", data: {} },
            { id: 2, type: "map", data: { title: "Find us on the map" } },
          ],
          aside: [{ id: 3, type: "enquiry_form", data: { title: "Send an enquiry" } }],
        },
      },
    ],
  },

  privacy: {
    key: "privacy",
    slug: "privacy",
    title: "Privacy policy",
    // Draft for the college to approve. Kept out of search results until it is approved.
    seo: { title: "Privacy policy", description: seoDescription("How VRR Degree College handles your information."), noindex: true },
    sections: [
      { id: 1, type: "page_header", data: { title: "Privacy policy", subtitle: "How we handle your information." } },
      {
        id: 2,
        type: "rich_text",
        data: {
          body: doc(
            p("Draft for approval by the college."),
            h("What we collect"),
            p("When you send the enquiry form we collect your name, mobile number, the course you are interested in and an optional message."),
            h("Why we collect it"),
            p("Only to call you back about admissions and answer your questions."),
            h("Who can see it"),
            ul("College staff who handle admissions.", "We do not sell your details or share them with advertisers."),
            h("How long we keep it"),
            p("Enquiries are deleted after 12 months."),
            h("Your choices"),
            p("You can ask the college office to show, correct or delete your enquiry at any time."),
            h("Cookies"),
            p("This website does not use advertising or tracking cookies."),
          ),
        },
      },
    ],
  },
};
