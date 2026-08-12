// Generates 250 realistic emails matching the ingestion schema,
// starting with the 12 worked examples from the challenge brief.

export function generateSampleEmails(count = 250) {
  const base_date = "2026-08-01";
  
  const brief_examples = [
    {
      "email_id": "em_brief_001",
      "thread_id": "th_brief_001",
      "message_index": 0,
      "from_name": "Suresh Kulkarni",
      "from_email": "s.kulkarni@meridiansteel.co.in",
      "to": "sales@company.com",
      "cc": ["procurement@meridiansteel.co.in"],
      "subject": "RFP - Enterprise Document Management System",
      "body": "Meridian Steel invites proposals for an enterprise DMS covering 4 plants and ~1,200 users. Indicative budget is Rs. 25 lakhs. Proposals must reach us by 12th August 2026.",
      "received_at": "2026-08-01T09:14:22+05:30",
      "attachments": ["RFP_DMS_2026.pdf"],
      "is_reply": false
    },
    {
      "email_id": "em_brief_002",
      "thread_id": "th_brief_002",
      "message_index": 0,
      "from_name": "Ankit Bose",
      "from_email": "ankit@railyardlogistics.in",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Quick demo request",
      "body": "Hi, we're a 30-person logistics startup in Pune... can we get a demo sometime next week? Nothing urgent. — Ankit Bose, Founder, Railyard Logistics",
      "received_at": "2026-08-01T11:02:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_003",
      "thread_id": "th_brief_003",
      "message_index": 0,
      "from_name": "BHEL Procurement",
      "from_email": "bhel.procure@bhel.co.in",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Tender Notice No. BHEL/PROC/2026/0847",
      "body": "Tender Notice No. BHEL/PROC/2026/0847. Bharat Heavy Electricals Limited invites bids for supply of analytics software licences. Estimated value: Rs. 6,50,000. Last date for bid submission: 03-08-2026, 1700 hrs IST.",
      "received_at": "2026-08-01T14:20:00+05:30",
      "attachments": ["specs.pdf"],
      "is_reply": false
    },
    {
      "email_id": "em_brief_004",
      "thread_id": "th_brief_004",
      "message_index": 0,
      "from_name": "Nandita Reddy",
      "from_email": "nandita@saassummit.in",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Sponsorship confirmation needed",
      "body": "We're finalising sponsors for the India SaaS Summit in Bengaluru. Gold tier is ₹4,00,000 and includes a keynote slot. We need confirmation by tomorrow EOD as we're going to print. — Nandita Reddy, Sponsorship Lead",
      "received_at": "2026-08-02T16:45:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_005",
      "thread_id": "th_brief_005",
      "message_index": 0,
      "from_name": "Vantage Cloud Services",
      "from_email": "billing@vantagecloud.com",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Invoice INV-2026-0331 - Net 30 Overdue",
      "body": "Please find attached invoice INV-2026-0331 for Rs. 1,18,000 (incl. 18% GST) against PO-88214. Kindly process — payment terms were Net 30 and this is now 12 days overdue. Also, our GSTIN has changed, updated details attached.",
      "received_at": "2026-08-03T10:00:00+05:30",
      "attachments": ["INV_2026_0331.pdf"],
      "is_reply": false
    },
    {
      "email_id": "em_brief_006",
      "thread_id": "th_brief_006",
      "message_index": 0,
      "from_name": "Zenith Cloud Partners",
      "from_email": "partner@zenithcloud.com",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Partnership Proposal - Salesforce Implementation",
      "body": "We're a Salesforce implementation partner across MEA with 40+ enterprise clients. We'd like to explore reselling your platform in the region, or a technical integration at minimum. Who handles partnerships?",
      "received_at": "2026-08-03T11:15:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_007",
      "thread_id": "th_brief_007",
      "message_index": 0,
      "from_name": "Raghav Sharma",
      "from_email": "raghav@northbridge.in",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Out of Office until 14th August",
      "body": "I am out of office until 14th August with limited access to email. For urgent matters please contact my colleague at raghav@northbridge.in. — Sent from Outlook",
      "received_at": "2026-08-03T08:00:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_008",
      "thread_id": "th_brief_008",
      "message_index": 0,
      "from_name": "SEO Agency",
      "from_email": "sales@seobooster.com",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Improve organic search rankings",
      "body": "Hi, I noticed your website isn't ranking on page 1 for key terms. We've helped 200+ SaaS companies 3x their organic traffic. We do content marketing, PR outreach, and webinar promotion. Free audit attached — interested in a quick 15 min call?",
      "received_at": "2026-08-04T09:30:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_009",
      "thread_id": "th_brief_009",
      "message_index": 0,
      "from_name": "B2B Growth Weekly",
      "from_email": "newsletter@b2bgrowth.com",
      "to": "sales@company.com",
      "cc": [],
      "subject": "The B2B Growth Weekly — Issue #212",
      "body": "The B2B Growth Weekly — Issue #212. In this edition: why PLG is stalling, 5 pricing experiments that worked, and a teardown of Figma's onboarding. [Unsubscribe]",
      "received_at": "2026-08-04T12:00:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_010",
      "thread_id": "th_brief_001", // reply to Suresh
      "message_index": 1,
      "from_name": "Suresh Kulkarni",
      "from_email": "s.kulkarni@meridiansteel.co.in",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Re: RFP - Enterprise Document Management System",
      "body": "Correction to our earlier note — the board has approved an increased budget of Rs. 32 lakhs, and the submission deadline is advanced to 11th August. Apologies for the change.\n\nOn Sun, Aug 1, 2026 at 9:14 AM Suresh Kulkarni wrote:\n> Meridian Steel invites proposals...",
      "received_at": "2026-08-09T09:00:00+05:30",
      "attachments": [],
      "is_reply": true
    },
    {
      "email_id": "em_brief_011",
      "thread_id": "th_brief_011",
      "message_index": 0,
      "from_name": "Farhan Qureshi",
      "from_email": "f.qureshi@halcyonretail.com",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Platform Evaluation and Webinar",
      "body": "Hi — we met at your booth in Mumbai. Two things: (1) we'd like to evaluate your platform for our 800-person org, budget TBD but likely significant, and (2) our CMO wants to co-host a webinar with your team in September. Can you loop in the right people? — Farhan Qureshi, VP Strategy, Halcyon Retail",
      "received_at": "2026-08-05T10:00:00+05:30",
      "attachments": [],
      "is_reply": false
    },
    {
      "email_id": "em_brief_012",
      "thread_id": "th_brief_012",
      "message_index": 0,
      "from_name": "Kanhaiya Kumar",
      "from_email": "kanhaiya@dealerhub.in",
      "to": "sales@company.com",
      "cc": [],
      "subject": "Product network requirements",
      "body": "Bhai, humko aapka product chahiye for our dealer network. Around 150 users honge. Budget approx 1.2 cr allocated hai for this FY. Kab connect kar sakte hain? Thoda jaldi, board review 20th ko hai.",
      "received_at": "2026-08-05T16:30:00+05:30",
      "attachments": [],
      "is_reply": false
    }
  ];

  const emails = [...brief_examples];

  // Synthetically generate the remaining emails to reach count total
  const companies = ["Infotech Solutions", "Nexus Corp", "Skyline Ventures", "Global Trades", "Apex Builders", "Green Energy Pvt Ltd", "Pro Consulting", "Alpha FinTech"];
  const names = ["Rajesh Gupta", "Meenakshi Sen", "Vijay Kumar", "Pooja Hegde", "Sanjay Dutt", "Arjun Kapoor", "Karan Johar", "Preity Zinta"];
  const categories = ["rfp", "demo", "psu", "marketing", "invoice", "reseller", "ooo", "spam", "newsletter", "reply", "conflict"];

  for (let i = 13; i <= count; i++) {
    const category = categories[Math.floor(Math.random() * categories.length)];
    const base_company = companies[Math.floor(Math.random() * companies.length)];
    const company = `${base_company} ${Math.floor(Math.random() * 800 + 100)}`;
    const sender = names[Math.floor(Math.random() * names.length)];
    const email_domain = company.toLowerCase().replace(/[^a-z0-9]/g, "") + ".com";
    const from_email = `${sender.toLowerCase().replace(/\s+/g, "")}@${email_domain}`;

    const date_offset = Math.floor(Math.random() * 6);
    const hour_offset = Math.floor(Math.random() * 24);
    const received_at = `2026-08-0${1 + date_offset}T${hour_offset.toString().padStart(2, "0")}:15:00+05:30`;

    let email = {
      "email_id": `em_synth_${i.toString().padStart(3, "0")}`,
      "thread_id": `th_synth_${i.toString().padStart(3, "0")}`,
      "message_index": 0,
      "from_name": sender,
      "from_email": from_email,
      "to": "sales@company.com",
      "cc": [],
      "subject": "",
      "body": "",
      "received_at": received_at,
      "attachments": [],
      "is_reply": false
    };

    if (category === "rfp") {
      const budget = Math.floor(Math.random() * 80) + 15; // 15 to 95 Lakhs
      const day = Math.floor(Math.random() * 10) + 10; // 10 to 20
      email.subject = `RFP Request - Enterprise Solutions for ${company}`;
      email.body = `Dear Sales Team,\n\n${company} is looking for a comprehensive document suite. We have budgeted Rs. ${budget} Lakhs for this initiative. Kindly submit your proposal by ${day}th August 2026.\n\nWarm regards,\n${sender}`;
    } else if (category === "demo") {
      const city = ["Pune", "Mumbai", "Bangalore", "Delhi", "Hyderabad", "Chennai"][Math.floor(Math.random() * 6)];
      email.subject = `Demo Request - ${company}`;
      email.body = `Hi Team,\n\nWe are a startup in ${city} and would love to schedule a demo of your product. Nothing urgent, next week works. Thanks!\n\n${sender}`;
    } else if (category === "psu") {
      const budget = Math.floor(Math.random() * 8) + 3; // 3 to 10 Lakhs
      const tender_id = Math.floor(Math.random() * 8000 + 1000);
      email.subject = `Tender for software licensing - NTPC procurement ID-${tender_id}`;
      email.body = `Tender announcement: NTPC Limited invites bids for software licensing. Total estimated value is Rs. ${budget},50,000. Last date for bid submission is 10-08-2026.`;
    } else if (category === "marketing") {
      const value = Math.floor(Math.random() * 4) + 2; // 2 to 5 Lakhs
      email.subject = `Webinar sponsorship collaboration proposal`;
      email.body = `Hi,\n\nWe are organizing the annual FinTech Conclave 2026. Sponsorship slots are open starting at Rs ${value},00,000. Let us know if you want to collaborate.\n\n${sender}`;
    } else if (category === "invoice") {
      const val = Math.floor(Math.random() * 150000) + 50000;
      const inv_id = Math.floor(Math.random() * 800 + 100);
      email.subject = `Overdue payment reminder - Invoice INV-2026-${inv_id}`;
      email.body = `Hello Finance team,\n\nKindly note invoice INV-2026-${inv_id} for Rs ${val.toLocaleString()} is still pending. This was due 10 days ago. Please pay immediately.\n\nRegards,\nAccounts Team`;
    } else if (category === "reseller") {
      const region = ["EMEA", "APAC", "LATAM", "US & Canada"][Math.floor(Math.random() * 4)];
      email.subject = `Channel partnership inquiry for ${region}`;
      email.body = `Hello,\n\nWe are a software reseller with client networks in ${region}. We'd like to explore reseller terms for your SaaS suite.\n\nThanks,\n${sender}`;
    } else if (category === "ooo") {
      const date = Math.floor(Math.random() * 10) + 12;
      email.subject = `Auto: Out of Office`;
      email.body = `Thank you for your email. I am out of the office until ${date}th August with no email access. For urgent issues contact support@${email_domain}.`;
    } else if (category === "spam") {
      email.subject = `Boost your website traffic - SEO promotion`;
      email.body = `Hello,\n\nWe noticed you are not ranking for key terms. We offer PR, content writing, SEO, and social marketing services. Let's hop on a quick 10 min call? [Unsubscribe]`;
    } else if (category === "newsletter") {
      const num = Math.floor(Math.random() * 300) + 100;
      email.subject = `SaaS Growth Newsletter #${num}`;
      email.body = `Here are the top SaaS growth trends for 2026. Tips on retention, churn, and scaling. Click here to unsubscribe.`;
    } else if (category === "reply") {
      const parent_num = i - 9;
      email.subject = `Re: RFP Request - Enterprise Solutions for ${companies[parent_num % companies.length]}`;
      email.thread_id = `th_synth_${parent_num.toString().padStart(3, "0")}`;
      email.message_index = 1;
      email.is_reply = true;
      const budget = Math.floor(Math.random() * 40) + 45; // 45 to 85 Lakhs
      email.body = `Quick update: our board approved a revised budget of ${budget} lakhs. Also, we need the RFP by 14th August 2026.\n\nOn Sun, Aug 1, 2026 at 10:15 AM wrote:\n> Dear Sales Team...`;
    } else if (category === "conflict") {
      email.subject = `Product Enquiry & Joint Webinar Collaboration`;
      email.body = `Dear Team,\n\nWe want to evaluate your system for our 200 user team, budget is not fixed yet. Additionally, our CMO would like to co-host a joint webinar. Who handles these? Thanks,\n${sender}`;
    }

    emails.push(email);
  }

  const run_suffix = Math.random().toString(36).substring(2, 6);
  return emails.slice(0, count).map(email => ({
    ...email,
    email_id: `${email.email_id}_${run_suffix}`,
    thread_id: `${email.thread_id}_${run_suffix}`
  }));
}
