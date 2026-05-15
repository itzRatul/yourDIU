/**
 * Mock data for NEXT_PUBLIC_USE_MOCK=true
 * Lets the frontend run and look complete without a backend.
 */
import type { Post, Notice, Notification, PDFSession } from "./api";

export const mockUser = {
  id: "mock-user-1",
  email: "ratul@diu.edu.bd",
  user_metadata: { full_name: "Ratul Hossen", avatar_url: null },
};

export const mockPosts: Post[] = [
  {
    id: "1", user_id: "mock-user-1",
    content: "আজকের CSE 101 ক্লাসটা ছিল দারুণ! ডেটা স্ট্রাকচারের মূল বিষয়গুলো বোঝা গেল।",
    likes_count: 12, comments_count: 3, created_at: new Date(Date.now() - 3600000).toISOString(),
    author: { full_name: "Ratul Hossen" }, is_liked: false,
  },
  {
    id: "2", user_id: "mock-user-2",
    content: "কেউ কি মিড সেমিস্টার পরীক্ষার রুটিন পেয়েছ? শেয়ার করো প্লিজ 🙏",
    likes_count: 7, comments_count: 5, created_at: new Date(Date.now() - 7200000).toISOString(),
    author: { full_name: "Tanvir Ahmed" }, is_liked: true,
  },
  {
    id: "3", user_id: "mock-user-3",
    content: "DIU library তে নতুন programming books এসেছে। সবাই দেখতে যাও!",
    likes_count: 24, comments_count: 8, created_at: new Date(Date.now() - 86400000).toISOString(),
    author: { full_name: "Nadia Islam" }, is_liked: false,
  },
];

export const mockNotices: Notice[] = [
  {
    id: "1", title: "মিড সেমিস্টার পরীক্ষার সময়সূচি প্রকাশিত",
    content: "CSE বিভাগের মিড সেমিস্টার পরীক্ষা ২০২৬ সালের জুন মাসে অনুষ্ঠিত হবে। বিস্তারিত নিচে দেওয়া হলো।",
    category: "exam", published_at: new Date(Date.now() - 86400000).toISOString(),
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: "2", title: "ভর্তি বিজ্ঞপ্তি ২০২৬-২৭",
    content: "Spring 2026-27 সেশনের ভর্তি কার্যক্রম শুরু হয়েছে। আগ্রহী শিক্ষার্থীরা অনলাইনে আবেদন করুন।",
    category: "admission", published_at: new Date(Date.now() - 172800000).toISOString(),
    created_at: new Date(Date.now() - 172800000).toISOString(),
  },
  {
    id: "3", title: "বার্ষিক ক্রীড়া প্রতিযোগিতা ২০২৬",
    content: "এ বছরের বার্ষিক ক্রীড়া প্রতিযোগিতা আগামী মাসে অনুষ্ঠিত হবে। সকল শিক্ষার্থীকে অংশগ্রহণের আমন্ত্রণ।",
    category: "event", published_at: new Date(Date.now() - 259200000).toISOString(),
    created_at: new Date(Date.now() - 259200000).toISOString(),
  },
];

export const mockNotifications: Notification[] = [
  { id: "1", title: "নতুন নোটিশ", body: "মিড সেমিস্টার পরীক্ষার সময়সূচি প্রকাশিত হয়েছে।", type: "notice", is_read: false, created_at: new Date(Date.now() - 3600000).toISOString() },
  { id: "2", title: "Community", body: "Tanvir Ahmed তোমার পোস্টে like করেছে।", type: "like", is_read: false, created_at: new Date(Date.now() - 7200000).toISOString() },
  { id: "3", title: "System", body: "তোমার প্রোফাইল আপডেট সফল হয়েছে।", type: "system", is_read: true, created_at: new Date(Date.now() - 86400000).toISOString() },
];

export const mockPDFSessions: PDFSession[] = [
  {
    id: "mock-session-1", filename: "data_structures.pdf", file_size: 2048576,
    page_count: 45, chunk_count: 120, status: "ready",
    summary: "**Main Topic**\nThis document covers fundamental data structures...",
    has_summary: true, expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
];

export const mockChatResponses = [
  "আমি yourDIU AI assistant। আপনাকে DIU সম্পর্কিত যেকোনো তথ্য দিতে পারব।",
  "DIU তে বর্তমানে বিভিন্ন বিভাগে পড়াশোনার সুযোগ রয়েছে। CSE, EEE, BBA সহ আরও অনেক বিষয় আছে।",
  "আপনার প্রশ্নের উত্তর দিতে পেরে খুশি হব। আরও কিছু জানতে চান?",
];
