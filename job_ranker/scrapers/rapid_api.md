```
import requests

url = "https://jsearch.p.rapidapi.com/search"

querystring = {"query":"developer jobs in chicago","page":"1","num_pages":"1","country":"us","date_posted":"all"}

headers = {
	"x-rapidapi-key": "3a7xxx",
	"x-rapidapi-host": "jsearch.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())
```

```
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "request_id": {
      "type": "string"
    },
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string"
        },
        "page": {
          "type": "integer"
        },
        "num_pages": {
          "type": "integer"
        },
        "date_posted": {
          "type": "string"
        },
        "country": {
          "type": "string"
        },
        "language": {
          "type": "string"
        }
      }
    },
    "data": {
      "type": "array",
      "items": {
        "type": "object"
      }
    }
  }
}
```


```
import requests

url = "https://indeed12.p.rapidapi.com/company/Ubisoft/jobs"

querystring = {"locality":"us","start":"1"}

headers = {
	"x-rapidapi-key": "3a7xxx",
	"x-rapidapi-host": "indeed12.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())
```


```
{
  "type": "object",
  "properties": {
    "count": {
      "type": "integer"
    },
    "hits": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "formatted_relative_time": {
            "type": "string"
          },
          "id": {
            "type": "string"
          },
          "link": {
            "type": "string"
          },
          "locality": {
            "type": "string"
          },
          "location": {
            "type": "string"
          },
          "title": {
            "type": "string"
          }
        }
      }
    },
    "indeed_final_url": {
      "type": "string"
    },
    "next_start": {
      "type": "integer"
    },
    "prev_start": {
      "type": "integer"
    }
  }
}
```



```
import requests

url = "https://jobs-search-api.p.rapidapi.com/"

headers = {
	"x-rapidapi-key": "3a7xxx",
	"x-rapidapi-host": "jobs-search-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers)

print(response.json())
```

```
import requests

url = "https://indeed-scraper-api.p.rapidapi.com/api/job"

payload = { "scraper": {
		"maxRows": 15,
		"query": "Developer",
		"location": "San Francisco",
		"jobType": "fulltime",
		"radius": "50",
		"sort": "relevance",
		"fromDays": "7",
		"country": "us"
	} }
headers = {
	"x-rapidapi-key": "3a7xxx",
	"x-rapidapi-host": "indeed-scraper-api.p.rapidapi.com",
	"Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())
```

```
{
  "state": "completed",
  "name": "indeed-scraper-queue",
  "data": {
    "scraper": {
      "maxRows": 15,
      "query": "Developer",
      "location": "San Francisco",
      "jobType": "fulltime",
      "radius": "50",
      "sort": "relevance",
      "fromDays": "7",
      "country": "us"
    }
  },
  "id": "gx8s69crjn13ub9glqvotixy",
  "progress": 100,
  "returnvalue": {
    "data": [
      {
        "title": "Software Developer",
        "jobType": "Full-time",
        "companyName": "Oracle",
        "companyUrl": "https://www.indeed.com/cmp/Oracle",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/7469a5861d5fac78de05b68853a2b2ee",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/6292c8d72ac5b8f69f4c099fcdff7d02",
        "rating": {
          "ariaContent": "3.8 out of 5 stars. Link to 7,359 company reviews (opens in a new tab)",
          "count": 7359,
          "countContent": "7,359 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 3.8,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Redwood City",
          "postalCode": "94065",
          "latitude": 37.530666,
          "longitude": -122.26243,
          "streetAddress": "500 Oracle Parkway",
          "formattedAddressLong": "Redwood City, CA 94065",
          "formattedAddressShort": "Redwood City, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [],
        "socialInsurance": [],
        "workingSystem": [],
        "attributes": [
          "Operating systems",
          "Computer Science",
          "Software troubleshooting",
          "Data structures",
          "Full-time",
          "Mid-level",
          "Java",
          "Master's degree",
          "C++",
          "Test cases",
          "Software architecture"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 69,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <p><b>Job Duties </b>: <i>Design, develop, troubleshoot and/or test/QA software. As a member of the software engineering division, apply knowledge of software architecture to perform tasks associated with developing, debugging, or designing software applications or operating systems according to provided design specifications. Build enhancements within an existing software architecture and/or suggest improvements to the architecture. May telecommute. (385.29717)<br> </i></p>\n <p></p>\n <p><i>Employer will accept a Master’s degree in Computer Science, Engineering, or related technical field. Position requires: </i></p>\n <ul>\n  <li><i>Data structures and algorithms; </i></li>\n  <li><i>Coding (Java or C++); </i></li>\n  <li><i>Debugging codebase; </i></li>\n  <li><i>Writing unit test cases; </i></li>\n  <li><i>Software architecture basic understanding; </i></li>\n  <li><i>Networking basic knowledge; </i></li>\n  <li><i>Operating Systems basic knowledge; and </i></li>\n  <li><i>Containerization basic knowledge. </i></li>\n </ul>\n <p>Career Level - IC2</p>\n</div><br>\n<div></div>",
        "descriptionText": "Job Duties : Design, develop, troubleshoot and/or test/QA software. As a member of the software engineering division, apply knowledge of software architecture to perform tasks associated with developing, debugging, or designing software applications or operating systems according to provided design specifications. Build enhancements within an existing software architecture and/or suggest improvements to the architecture. May telecommute. (385.29717)\n\nEmployer will accept a Master’s degree in Computer Science, Engineering, or related technical field. Position requires:\n\nData structures and algorithms;\nCoding (Java or C++);\nDebugging codebase;\nWriting unit test cases;\nSoftware architecture basic understanding;\nNetworking basic knowledge;\nOperating Systems basic knowledge; and\nContainerization basic knowledge.\n\nCareer Level - IC2",
        "age": "1 day ago",
        "datePublished": "2024-12-30T06:00:00.000Z",
        "expired": false,
        "jobKey": "8b38598b49120fa7",
        "source": "Oracle",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=8b38598b49120fa7",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 1
        }
      },
      {
        "title": "Content Developer for Apple Online Retail Engineering",
        "jobType": "Full-time",
        "companyName": "Apple",
        "companyUrl": "https://www.indeed.com/cmp/Apple",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/60c39b87a9a4eaa4df878c716840f84d",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/8c915d66415088a4c67d85ca195547dd",
        "rating": {
          "ariaContent": "4.1 out of 5 stars. Link to 13,469 company reviews (opens in a new tab)",
          "count": 13469,
          "countContent": "13,469 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Sunnyvale",
          "postalCode": null,
          "latitude": 37.36883,
          "longitude": -122.03635,
          "streetAddress": null,
          "formattedAddressLong": "Sunnyvale, CA",
          "formattedAddressShort": "Sunnyvale, CA"
        },
        "occupation": [
          "Content Strategy & Information Architecture Occupations",
          "Technology Occupations",
          "Web Design & User Experience Occupations"
        ],
        "benefits": [
          "Employee stock purchase plan",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "Retirement plan"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "Drupal",
          "Management",
          "SAP CRM",
          "WordPress",
          "Content management systems",
          "Employee stock purchase plan",
          "Full-time",
          "Git",
          "Mid-level",
          "E-commerce",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "SVN",
          "FileMaker",
          "2 years",
          "Communication skills",
          "Joomla",
          "Retirement plan"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 221,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <b>Summary</b><br> <br> Posted: Oct 25, 2024<br> <br> Weekly Hours: <b>40</b><br> <br> Role Number:<b>200573274</b><br> <br> The Online Retail Engineering team at Apple is seeking a hard-working, diligent Content Developer to handle data within our CMS and catalog management tools. This role will contribute to the success of the team by setting up content and guiding data infrastructure for new features and projects that the Apple Online Retail Engineering team delivers into production. Your work will be seen by millions of customers world-wide.<br> <br> <b>Description</b><br> <br> The Content Development team works on developing and improving features of the customer journey for all of Apple's e-commerce customers. In this role, you will work alongside many dedicated individuals who design, engineer, validate, and ship these phenomenal e-commerce features. Your role will be to set up and manage multiple types of data that are key to these new features. Your day-to-day would include setting up content, products, and media assets in the Publishing tools to support engineering projects and testing. You would track, package, and deploy all project data to production in accordance with sophisticated release plans. You will work proactively to achieve a bug-free environment, coordinate with off-shore and onshore resources to ensure tasks are completed efficiently, and produce detailed documentation of feature setup<br> <br> <b>Minimum Qualifications</b><br>\n <ul>\n  <li>2 or more years experience with CMS tools such as WordPress, Joomla, Drupal, or AEM</li>\n  <li>2 or more years experience with Catalog Management tools such as FileMaker, SAP CRM, or Salsify</li>\n  <li>2 or more years experience with global e-commerce shopping experience development and execution</li>\n  <li>Experience with a repository such as SVN or git</li>\n </ul><br> <b> Preferred Qualifications</b><br>\n <ul>\n  <li>Excellent written and verbal communication skills, attention to detail, and the ability to work with minimal supervision</li>\n  <li>Demonstrated experience working on large, multi-functional projects</li>\n  <li>Strong decision making and prioritization skills; have experience driving sophisticated production schedules with dependencies and challenging priorities</li>\n  <li>Ability to build rapport, credibility and influence across a large, matrixed organization</li>\n  <li>Comfortable upholding interpersonal values and standard methodologies, while balancing competing time-to-market pressures and maintaining business relationships</li>\n  <li>Possess a passion for effective communication, both written and verbal, with technical and non-technical multi-functional teams</li>\n  <li>Able to anticipate, troubleshoot, and resolve problems on the fly</li>\n  <li>Strong technical background, and an ability to collaborate optimally with engineers</li>\n </ul><br> <b> Pay &amp; Benefits</b><br>\n <ul>\n  At Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $143,100 and $214,500, and your base pay will depend on your skills, qualifications, experience, and location.  Apple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.  Note: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n </ul><br> More<br>\n <ul>\n  <li>Apple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.</li>\n </ul>\n</div>",
        "descriptionText": "Summary\n\nPosted: Oct 25, 2024\n\nWeekly Hours: 40\n\nRole Number:200573274\n\nThe Online Retail Engineering team at Apple is seeking a hard-working, diligent Content Developer to handle data within our CMS and catalog management tools. This role will contribute to the success of the team by setting up content and guiding data infrastructure for new features and projects that the Apple Online Retail Engineering team delivers into production. Your work will be seen by millions of customers world-wide.\n\nDescription\n\nThe Content Development team works on developing and improving features of the customer journey for all of Apple's e-commerce customers. In this role, you will work alongside many dedicated individuals who design, engineer, validate, and ship these phenomenal e-commerce features. Your role will be to set up and manage multiple types of data that are key to these new features. Your day-to-day would include setting up content, products, and media assets in the Publishing tools to support engineering projects and testing. You would track, package, and deploy all project data to production in accordance with sophisticated release plans. You will work proactively to achieve a bug-free environment, coordinate with off-shore and onshore resources to ensure tasks are completed efficiently, and produce detailed documentation of feature setup\n\nMinimum Qualifications\n\n2 or more years experience with CMS tools such as WordPress, Joomla, Drupal, or AEM\n2 or more years experience with Catalog Management tools such as FileMaker, SAP CRM, or Salsify\n2 or more years experience with global e-commerce shopping experience development and execution\nExperience with a repository such as SVN or git\n\nPreferred Qualifications\n\nExcellent written and verbal communication skills, attention to detail, and the ability to work with minimal supervision\nDemonstrated experience working on large, multi-functional projects\nStrong decision making and prioritization skills; have experience driving sophisticated production schedules with dependencies and challenging priorities\nAbility to build rapport, credibility and influence across a large, matrixed organization\nComfortable upholding interpersonal values and standard methodologies, while balancing competing time-to-market pressures and maintaining business relationships\nPossess a passion for effective communication, both written and verbal, with technical and non-technical multi-functional teams\nAble to anticipate, troubleshoot, and resolve problems on the fly\nStrong technical background, and an ability to collaborate optimally with engineers\n\nPay & Benefits\n\nAt Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $143,100 and $214,500, and your base pay will depend on your skills, qualifications, experience, and location.\n\nApple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.\n\nNote: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n\nMore\n\nApple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.",
        "age": "6 days ago",
        "datePublished": "2024-12-26T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 214500,
          "salaryMin": 143100,
          "salarySource": "EXTRACTION",
          "salaryText": "$143,100 - $214,500 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "7ad3fb2ac75e06a5",
        "source": "Apple",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=7ad3fb2ac75e06a5",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 2
        }
      },
      {
        "title": "Software Engineer II",
        "jobType": "Full-time",
        "companyName": "Microsoft",
        "companyUrl": "https://www.indeed.com/cmp/Microsoft",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/88813b3f866a5b58c9685073e3b87e05",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/7461d01cfaa2be8b173212be5e85f01a",
        "rating": {
          "ariaContent": "4.2 out of 5 stars. Link to 8,646 company reviews (opens in a new tab)",
          "count": 8646,
          "countContent": "8,646 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.2,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Mountain View",
          "postalCode": "94043",
          "latitude": 37.4106,
          "longitude": -122.07022,
          "streetAddress": "1045 La Avenida Street",
          "formattedAddressLong": "Mountain View, CA 94043",
          "formattedAddressShort": "Mountain View, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [],
        "socialInsurance": [],
        "workingSystem": [],
        "attributes": [
          "Azure",
          "Law",
          "Computer Science",
          "Web development",
          "C#",
          "Microsoft SQL Server",
          "Full-time",
          "Mid-level",
          "Java",
          "SQL",
          "C++",
          "C",
          "Bachelor's degree",
          "JavaScript",
          "Data analytics",
          "2 years",
          "Python",
          "jQuery",
          "HTML",
          "T-SQL"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 172,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <div>\n  The Bing Metrics Team has a unique opportunity to join Bing Search, a global search engine powering billions of searches daily, as a <b>Software Engineer II</b>.\n </div>\n <div>\n  <br> <br> The Bing Metrics team is looking for passionate full stack developers and data scientists to work on a new generation of metrics and quality control for the entire Bing search landscape. The team ensures that Bing shows high-quality, error-free, and authoritative results using a variety of different approaches. We routinely query petabytes of user activity data to uncover potential issues in user interactions with the search engine. We build complex pipelines including crowd judging and leverage the power of large language models (LLMs) to verify our suspicions. LLMs allow us to evaluate the quality of search results at multiple levels: query, answer, whole page and generate insights for the teams who are responsible for this experience.\n </div>\n <div>\n  <br> As a part of an international and distributed team you will be responsible for identifying issues and implementing search quality metrics within Bing Search. The job provides you with the opportunity to work with multiple teams across the entire Bing organization (&gt;80 different teams) and greatly influence search engine relevance and search result quality. We are an established core team in Bing with very high visibility and impact.\n </div>\n <div>\n  <br> We are looking for a talented engineer who is detail oriented, with a passion to work with large scale computing, loves to design complex data pipelines built on top of LLM models, create new tools for running multi-step prompts to evaluate search engine quality and generate actionable insights for teams. If your blood boils when you see bad search results and you wish you could do something about them, this is the job for you!<br> <br> Microsoft’s mission is to empower every person and every organization on the planet to achieve more. As employees we come together with a growth mindset, innovate to empower others, and collaborate to realize our shared goals. Each day we build on our values of respect, integrity, and accountability to create a culture of inclusion where everyone can thrive at work and beyond.\n </div>\n <h2 class=\"jobSectionHeader\"><b> Responsibilities</b></h2>\n <ul>\n  <li>Build tools and pipelines with Bing Logs using Big Data platforms.</li>\n  <li>Design and implement E2E pipelines (from data collection, evaluation and result display).</li>\n  <li>Design and implement tools for LLM models, engineer prompts for textual and multi-model LLMs for data processing and insight generation.</li>\n  <li>Design and implement creative visualization for your results.</li>\n </ul>\n <h2 class=\"jobSectionHeader\"><b> Qualifications</b></h2>\n <div>\n  <b> Required Qualifications:</b>\n </div>\n <ul>\n  <li>Bachelor's Degree in Computer Science or related technical field AND 2+ years technical engineering experience with coding in languages including, but not limited to, C, C++, C#, Java, JavaScript, or Python<br>\n   <ul>\n    <li>OR equivalent experience.</li>\n   </ul></li>\n  <li>2+ years of experience in writing automation code with Chromium and Puppeteer.</li>\n  <li>2+ years of experience in developing solutions on Azure, utilizing Functions, WebJobs, Cloud Services, Azure Database, and Queues.</li>\n  <li>2+ years of experience with SQL, T-SQL, SQL Server.</li>\n </ul>\n <div></div>\n <div>\n  <b><br> Additional or Preferred Qualifications:</b>\n </div>\n <ul>\n  <li>3+ years of experience with modern web development [HTML, JavaScript, jQuery].</li>\n  <li>Experience in testing and relevance evaluation.</li>\n  <li>Experience or deep interest in Large-Language Models (ChatGPT).</li>\n  <li>Experience in (big) data and data analytics.</li>\n </ul>\n <div></div>\n <div>\n  <br> Software Engineering IC3 - The typical base pay range for this role across the U.S. is USD $98,300 - $193,200 per year. There is a different range applicable to specific work locations, within the San Francisco Bay area and New York City metropolitan area, and the base pay range for this role in those locations is USD $127,200 - $208,800 per year.\n </div>\n <div>\n </div>\n <div>\n  Certain roles may be eligible for benefits and other compensation. Find additional benefits and pay information here: https://careers.microsoft.com/us/en/us-corporate-pay\n </div>\n <div></div>\n <div>\n  <br>\n </div>\n <div>\n  Microsoft will accept applications for the role until January 7, 2025.\n </div><br>\n <div></div> Microsoft is an equal opportunity employer. Consistent with applicable law, all qualified applicants will receive consideration for employment without regard to age, ancestry, citizenship, color, family or medical care leave, gender identity or expression, genetic information, immigration status, marital status, medical condition, national origin, physical or mental disability, political affiliation, protected veteran or military status, race, ethnicity, religion, sex (including pregnancy), sexual orientation, or any other characteristic protected by applicable local laws, regulations and ordinances. If you need assistance and/or a reasonable accommodation due to a disability during the application process, read more about requesting accommodations.\n</div>",
        "descriptionText": "The Bing Metrics Team has a unique opportunity to join Bing Search, a global search engine powering billions of searches daily, as a Software Engineer II.\n\nThe Bing Metrics team is looking for passionate full stack developers and data scientists to work on a new generation of metrics and quality control for the entire Bing search landscape. The team ensures that Bing shows high-quality, error-free, and authoritative results using a variety of different approaches. We routinely query petabytes of user activity data to uncover potential issues in user interactions with the search engine. We build complex pipelines including crowd judging and leverage the power of large language models (LLMs) to verify our suspicions. LLMs allow us to evaluate the quality of search results at multiple levels: query, answer, whole page and generate insights for the teams who are responsible for this experience.\n\nAs a part of an international and distributed team you will be responsible for identifying issues and implementing search quality metrics within Bing Search. The job provides you with the opportunity to work with multiple teams across the entire Bing organization (>80 different teams) and greatly influence search engine relevance and search result quality. We are an established core team in Bing with very high visibility and impact.\n\nWe are looking for a talented engineer who is detail oriented, with a passion to work with large scale computing, loves to design complex data pipelines built on top of LLM models, create new tools for running multi-step prompts to evaluate search engine quality and generate actionable insights for teams. If your blood boils when you see bad search results and you wish you could do something about them, this is the job for you!\n\nMicrosoft’s mission is to empower every person and every organization on the planet to achieve more. As employees we come together with a growth mindset, innovate to empower others, and collaborate to realize our shared goals. Each day we build on our values of respect, integrity, and accountability to create a culture of inclusion where everyone can thrive at work and beyond.\n\nResponsibilities\nBuild tools and pipelines with Bing Logs using Big Data platforms.\nDesign and implement E2E pipelines (from data collection, evaluation and result display).\nDesign and implement tools for LLM models, engineer prompts for textual and multi-model LLMs for data processing and insight generation.\nDesign and implement creative visualization for your results.\nQualifications\n\nRequired Qualifications:\n\nBachelor's Degree in Computer Science or related technical field AND 2+ years technical engineering experience with coding in languages including, but not limited to, C, C++, C#, Java, JavaScript, or Python\n\nOR equivalent experience.\n2+ years of experience in writing automation code with Chromium and Puppeteer.\n2+ years of experience in developing solutions on Azure, utilizing Functions, WebJobs, Cloud Services, Azure Database, and Queues.\n2+ years of experience with SQL, T-SQL, SQL Server.\n\nAdditional or Preferred Qualifications:\n\n3+ years of experience with modern web development [HTML, JavaScript, jQuery].\nExperience in testing and relevance evaluation.\nExperience or deep interest in Large-Language Models (ChatGPT).\nExperience in (big) data and data analytics.\n\nSoftware Engineering IC3 - The typical base pay range for this role across the U.S. is USD $98,300 - $193,200 per year. There is a different range applicable to specific work locations, within the San Francisco Bay area and New York City metropolitan area, and the base pay range for this role in those locations is USD $127,200 - $208,800 per year.\n\nCertain roles may be eligible for benefits and other compensation. Find additional benefits and pay information here: https://careers.microsoft.com/us/en/us-corporate-pay\n\nMicrosoft will accept applications for the role until January 7, 2025.\n\nMicrosoft is an equal opportunity employer. Consistent with applicable law, all qualified applicants will receive consideration for employment without regard to age, ancestry, citizenship, color, family or medical care leave, gender identity or expression, genetic information, immigration status, marital status, medical condition, national origin, physical or mental disability, political affiliation, protected veteran or military status, race, ethnicity, religion, sex (including pregnancy), sexual orientation, or any other characteristic protected by applicable local laws, regulations and ordinances. If you need assistance and/or a reasonable accommodation due to a disability during the application process, read more about requesting accommodations.",
        "age": "Just posted",
        "datePublished": "2024-12-31T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 208800,
          "salaryMin": 98300,
          "salarySource": "EXTRACTION",
          "salaryText": "$98,300 - $208,800 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "6d37fee89de8209f",
        "source": "Microsoft",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=6d37fee89de8209f",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 3
        }
      },
      {
        "title": "C++ Developer",
        "jobType": "Full-time",
        "companyName": "UST Global",
        "companyUrl": "https://www.indeed.com/cmp/Ust-2",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/07ea3746bef405d42fc8185242f1222b",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/cf90c56bbfeccf3ba0e9613e084da868",
        "rating": {
          "ariaContent": "3.7 out of 5 stars. Link to 1,042 company reviews (opens in a new tab)",
          "count": 1042,
          "countContent": "1,042 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 3.7,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Santa Clara",
          "postalCode": null,
          "latitude": 37.35411,
          "longitude": -121.95524,
          "streetAddress": null,
          "formattedAddressLong": "Santa Clara, CA",
          "formattedAddressShort": "Santa Clara, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [
          "Paid jury duty",
          "Health savings account",
          "Paid holidays",
          "Disability insurance",
          "Health insurance",
          "Dental insurance",
          "Flexible spending account",
          "Vision insurance",
          "401(k) matching",
          "Bereavement leave",
          "Life insurance",
          "Paid sick time"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "MATLAB",
          "TCP",
          "Paid jury duty",
          "Health savings account",
          "Software troubleshooting",
          "Visual Studio",
          "C#",
          "Paid holidays",
          "Full-time",
          "Disability insurance",
          "Mid-level",
          ".NET",
          "Health insurance",
          "Dental insurance",
          "Flexible spending account",
          "C++",
          "C",
          "REST",
          "Fair chance",
          "Vision insurance",
          "401(k) matching",
          "Multithreading",
          "gRPC",
          "Bereavement leave",
          "Life insurance",
          "Paid sick time"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 6,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div></div>\n<div>\n <div>\n  <div>\n   <div>\n    <ul>\n     <div>\n      10 Openings\n     </div>\n     <div>\n      Santa Clara\n     </div>\n    </ul>\n   </div>\n   <p></p>\n   <div>\n    <br>\n    <div>\n     <div>\n     </div>\n    </div>\n   </div>\n  </div>\n  <div></div>\n  <div>\n   <h3 class=\"jobSectionHeader\"><b>Role description</b></h3>\n   <div>\n    <p><b>C++ Developer</b></p>\n    <p><b> Lead I - Embedded Software</b></p><br>\n    <p></p>\n    <p><b> Who We Are:</b></p>\n    <p>Born digital, UST transforms lives through the power of technology. We walk alongside our clients and partners, embedding innovation and agility into everything they do. We help them create transformative experiences and human-centered solutions for a better world.</p>\n    <p>UST is a mission-driven group of 29,000+ practical problem solvers and creative thinkers in more than 30 countries. Our entrepreneurial teams are empowered to innovate, act nimbly, and create a lasting and sustainable impact for our clients, their customers, and the communities in which we live.</p>\n    <p>With us, you’ll create a boundless impact that transforms your career—and the lives of people across the world.</p>\n    <p>Visit us at UST.com.</p><br>\n    <p></p>\n    <p><b> You Are:</b></p>\n    <p>UST is searching for a C++ Developer who will design, prototype, and develop moderately difficult software solutions for semiconductor equipment components and devices.</p><br>\n    <p></p>\n    <p><b> The Opportunity:</b></p>\n    <ul>\n     <li>Designs common software modules and libraries for use across multiple products.</li>\n    </ul>\n    <ul>\n     <li>Troubleshoots a variety of moderately difficult software problems. Designs and implements bug fixes.</li>\n    </ul>\n    <p>· Defines software specifications · Suggests and implements improvements to the development and troubleshooting process.</p>\n    <ul>\n     <li>Develops software documentation.</li>\n    </ul>\n    <ul>\n     <li>Contributes to technical review boards for assigned programs.</li>\n    </ul>\n    <ul>\n     <li>Interfaces with internal and external customers for requirement analysis, project schedule and software troubleshooting</li>\n    </ul><br>\n    <p></p>\n    <p>This position description identifies the responsibilities and tasks typically associated with the performance of the position. Other relevant essential functions may be required.</p><br>\n    <p></p>\n    <p><b> What You </b><b>Need:</b></p>\n    <ul>\n     <li>Proficiency and experience in C and C++ are required.</li>\n    </ul>\n    <ul>\n     <li>In addition, programming experience in several of the following areas is desired: - Real-time Control</li>\n    </ul>\n    <ul>\n     <li>Motion Control - Embedded Programming</li>\n    </ul>\n    <ul>\n     <li>I/O (synchronous and asynchronous) - multi-threading, performance profiling - C#, .NET</li>\n    </ul>\n    <ul>\n     <li>gRPC, REST, TCP sockets - Visual Studio</li>\n    </ul>\n    <ul>\n     <li>Source Control - Matlab</li>\n    </ul><br>\n    <p></p>\n    <p>Compensation can differ depending on factors including but not limited to the specific office location, role, skill set, education, and level of experience. UST provides a reasonable range of compensation for roles that may be hired in various U.S. markets as set forth below.</p>\n    <p><b> Role Location: </b>California</p>\n    <p><b> Compensation Range: </b>$60,800-$91,200</p><br>\n    <p></p>\n    <p><b> Benefits</b></p>\n    <p>Full-time, regular employees accrue a minimum of 10 days of paid vacation per year, receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year), 10 paid holidays, and are eligible for paid bereavement leave and jury duty. They are eligible to participate in the Company’s 401(k) Retirement Plan with employer matching. They and their dependents residing in the US are eligible for medical, dental, and vision insurance, as well as the following Company-paid Employee Only benefits: basic life insurance, accidental death and disability insurance, and short- and long-term disability benefits. Regular employees may purchase additional voluntary short-term disability benefits, and participate in a Health Savings Account (HSA) as well as a Flexible Spending Account (FSA) for healthcare, dependent child care, and/or commuting expenses as allowable under IRS guidelines. Benefits offerings vary in Puerto Rico.</p>\n    <p>Part-time employees receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year) and are eligible to participate in the Company’s 401(k) Retirement Plan with employer matching.</p>\n    <p>Full-time temporary employees receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year) and are eligible to participate in the Company’s 401(k) program with employer matching. They and their dependents residing in the US are eligible for medical, dental, and vision insurance.</p>\n    <p>Part-time temporary employees receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year).</p>\n    <p>All US employees who work in a state or locality with more generous paid sick leave benefits than specified here will receive the benefit of those sick leave laws.</p><br>\n    <p></p>\n    <p><b> What We Believe:</b></p>\n    <p>We proudly embrace the values that have shaped UST since day one. We build our culture of Humility, Humanity, and Integrity. These values inspire us to nurture a people-first, human centric culture that fosters diversity, prioritizes sustainable solutions, and keeps our people and clients at the forefront of all decisions.</p>\n    <p><b> Humility:</b></p>\n    <p>We will listen, learn, be empathetic and help selflessly in our interactions with everyone.</p>\n    <p><b> Humanity:</b></p>\n    <p>Through business, we will better the lives of those less fortunate than ourselves.</p>\n    <p><b> Integrity:</b></p>\n    <p>We honor our commitments and act with responsibility in all our relationships.</p><br>\n    <div></div>\n    <div>\n     <b> Equal Employment Opportunity Statement</b>\n    </div>\n    <div>\n     <br> UST is an Equal Opportunity Employer.\n    </div><br>\n    <div></div>\n    <p>All qualified applicants will receive consideration for employment without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, status as a protected veteran, or any other applicable characteristics protected by law. We will consider qualified applicants with arrest or conviction records in accordance with state and local laws and “fair chance” ordinances.</p>\n    <div>\n     UST reserves the right to periodically redefine your roles and responsibilities based on the requirements of the organization and/or your performance.\n    </div><br>\n    <div></div>\n    <div>\n     #UST\n    </div>\n    <div>\n     #CB\n    </div>\n   </div>\n   <h3 class=\"jobSectionHeader\"><b>Skills</b></h3>\n   <div>\n    <p>C,C++,Programming</p>\n   </div>\n   <h3 class=\"jobSectionHeader\"><b>Benefits</b></h3>\n   <h3 class=\"jobSectionHeader\"><p><b>Compensation range: $ 60,800.00 to 91,200.00 per year</b></p></h3>\n  </div>\n </div>\n</div>\n<p></p> <br>\n<div>\n <h3 class=\"jobSectionHeader\"><b>About UST</b></h3>\n <div>\n  UST is a global digital transformation solutions provider. For more than 20 years, UST has worked side by side with the world’s best companies to make a real impact through transformation. Powered by technology, inspired by people and led by purpose, UST partners with their clients from design to operation. With deep domain expertise and a future-proof philosophy, UST embeds innovation and agility into their clients’ organizations. With over 30,000 employees in 30 countries, UST builds for boundless impact—touching billions of lives in the process.\n </div>\n</div>",
        "descriptionText": "10 Openings\n Santa Clara\n\nRole description\n\nC++ Developer\n\nLead I - Embedded Software\n\nWho We Are:\n\nBorn digital, UST transforms lives through the power of technology. We walk alongside our clients and partners, embedding innovation and agility into everything they do. We help them create transformative experiences and human-centered solutions for a better world.\n\nUST is a mission-driven group of 29,000+ practical problem solvers and creative thinkers in more than 30 countries. Our entrepreneurial teams are empowered to innovate, act nimbly, and create a lasting and sustainable impact for our clients, their customers, and the communities in which we live.\n\nWith us, you’ll create a boundless impact that transforms your career—and the lives of people across the world.\n\nVisit us at UST.com.\n\nYou Are:\n\nUST is searching for a C++ Developer who will design, prototype, and develop moderately difficult software solutions for semiconductor equipment components and devices.\n\nThe Opportunity:\n\n· Designs common software modules and libraries for use across multiple products.\n\n· Troubleshoots a variety of moderately difficult software problems. Designs and implements bug fixes.\n\n· Defines software specifications · Suggests and implements improvements to the development and troubleshooting process.\n\n· Develops software documentation.\n\n· Contributes to technical review boards for assigned programs.\n\n· Interfaces with internal and external customers for requirement analysis, project schedule and software troubleshooting\n\nThis position description identifies the responsibilities and tasks typically associated with the performance of the position. Other relevant essential functions may be required.\n\nWhat You Need:\n\n· Proficiency and experience in C and C++ are required.\n\n· In addition, programming experience in several of the following areas is desired: - Real-time Control\n\n· Motion Control - Embedded Programming\n\n· I/O (synchronous and asynchronous) - multi-threading, performance profiling - C#, .NET\n\n· gRPC, REST, TCP sockets - Visual Studio\n\n· Source Control - Matlab\n\nCompensation can differ depending on factors including but not limited to the specific office location, role, skill set, education, and level of experience. UST provides a reasonable range of compensation for roles that may be hired in various U.S. markets as set forth below.\n\nRole Location: California\n\nCompensation Range: $60,800-$91,200\n\nBenefits\n\nFull-time, regular employees accrue a minimum of 10 days of paid vacation per year, receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year), 10 paid holidays, and are eligible for paid bereavement leave and jury duty. They are eligible to participate in the Company’s 401(k) Retirement Plan with employer matching. They and their dependents residing in the US are eligible for medical, dental, and vision insurance, as well as the following Company-paid Employee Only benefits: basic life insurance, accidental death and disability insurance, and short- and long-term disability benefits. Regular employees may purchase additional voluntary short-term disability benefits, and participate in a Health Savings Account (HSA) as well as a Flexible Spending Account (FSA) for healthcare, dependent child care, and/or commuting expenses as allowable under IRS guidelines. Benefits offerings vary in Puerto Rico.\n\nPart-time employees receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year) and are eligible to participate in the Company’s 401(k) Retirement Plan with employer matching.\n\nFull-time temporary employees receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year) and are eligible to participate in the Company’s 401(k) program with employer matching. They and their dependents residing in the US are eligible for medical, dental, and vision insurance.\n\nPart-time temporary employees receive 6 days of paid sick leave each year (pro-rated for new hires throughout the year).\n\nAll US employees who work in a state or locality with more generous paid sick leave benefits than specified here will receive the benefit of those sick leave laws.\n\nWhat We Believe:\n\nWe proudly embrace the values that have shaped UST since day one. We build our culture of Humility, Humanity, and Integrity. These values inspire us to nurture a people-first, human centric culture that fosters diversity, prioritizes sustainable solutions, and keeps our people and clients at the forefront of all decisions.\n\nHumility:\n\nWe will listen, learn, be empathetic and help selflessly in our interactions with everyone.\n\nHumanity:\n\nThrough business, we will better the lives of those less fortunate than ourselves.\n\nIntegrity:\n\nWe honor our commitments and act with responsibility in all our relationships.\n\nEqual Employment Opportunity Statement\n\nUST is an Equal Opportunity Employer.\n\nAll qualified applicants will receive consideration for employment without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, status as a protected veteran, or any other applicable characteristics protected by law. We will consider qualified applicants with arrest or conviction records in accordance with state and local laws and “fair chance” ordinances.\n\nUST reserves the right to periodically redefine your roles and responsibilities based on the requirements of the organization and/or your performance.\n\n#UST\n\n#CB\n\nSkills\n\nC,C++,Programming\n\nBenefits\n\nCompensation range: $ 60,800.00 to 91,200.00 per year\nAbout UST\n\nUST is a global digital transformation solutions provider. For more than 20 years, UST has worked side by side with the world’s best companies to make a real impact through transformation. Powered by technology, inspired by people and led by purpose, UST partners with their clients from design to operation. With deep domain expertise and a future-proof philosophy, UST embeds innovation and agility into their clients’ organizations. With over 30,000 employees in 30 countries, UST builds for boundless impact—touching billions of lives in the process.",
        "age": "Just posted",
        "datePublished": "2024-12-31T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 91200,
          "salaryMin": 60800,
          "salarySource": "EXTRACTION",
          "salaryText": "$60,800 - $91,200 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "1441c6fcc161c09b",
        "source": "UST Global",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=1441c6fcc161c09b",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 4
        }
      },
      {
        "title": "Software Developer in Test - Swift Platform Experience",
        "jobType": "Full-time",
        "companyName": "Apple",
        "companyUrl": "https://www.indeed.com/cmp/Apple",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/60c39b87a9a4eaa4df878c716840f84d",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/8c915d66415088a4c67d85ca195547dd",
        "rating": {
          "ariaContent": "4.1 out of 5 stars. Link to 13,469 company reviews (opens in a new tab)",
          "count": 13469,
          "countContent": "13,469 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Cupertino",
          "postalCode": null,
          "latitude": 37.323,
          "longitude": -122.03218,
          "streetAddress": null,
          "formattedAddressLong": "Cupertino, CA",
          "formattedAddressShort": "Cupertino, CA"
        },
        "occupation": [
          "Technology Infrastructure Engineers",
          "Software Development Occupations",
          "Technology Infrastructure & Security Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations",
          "Systems & Applications Engineers & Analysts"
        ],
        "benefits": [
          "Employee stock purchase plan",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "Retirement plan"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "Management",
          "Computer Science",
          "Bachelor of Science",
          "Employee stock purchase plan",
          "Full-time",
          "Objective-C",
          "Mid-level",
          "Master's degree",
          "Health insurance",
          "Dental insurance",
          "Quality assurance",
          "RSU",
          "Bachelor's degree",
          "Continuous integration",
          "Software development",
          "APIs",
          "Integration testing",
          "Swift",
          "2 years",
          "Communication skills",
          "Debugging",
          "Retirement plan"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 83,
        "numOfCandidates": 5,
        "postedToday": true,
        "descriptionHtml": "<div>\n <b>Summary</b><br> <br> Posted: Oct 31, 2024<br> <br> Weekly Hours: <b>40</b><br> <br> Role Number:<b>200576722</b><br> <br> The Swift Platforms Experience team is looking for a driven and dedicated Software Engineer in Test. Our team is responsible for testing and ensuring the quality of major frameworks and tooling including Foundation, UIKit, SwiftUI, Swift Charts and Xcode Previews. You’ll be working directly with the talented Software Engineers and Quality Assurance Engineers responsible for the building blocks of apps across all of Apple’s platforms! Help us build applications, infrastructure, and tooling to validate the quality of our APIs in creative ways. The job responsibilities include: building, scaling, and maintaining XCTests &amp; XCUITests across our projects; testing our framework APIs; and, building validation tools to continuously improve the Quality Engineering Process. To ensure the best developer experience, you will also be responsible for testing framework behavior in our external developer tools such as Xcode Previews. You will be part of a Quality Engineering team that works and collaborates closely with the Engineering teams to create and ship exciting new features across Apple’s platforms. Our ideal candidate has a passion for code quality, continuously learning, facing new challenges, and values the third party developer experience.<br> <br> <b>Description</b><br> <br> - Gain a deep understanding of the design, requirements and architecture within the Swift Platform Experience frameworks - Devise and execute a testing strategy for features created by the Swift Platform Experience team - Provide functional and integration quality assurance testing for features across all of Apple’s platforms - Explore novel approaches to build or improve test frameworks, automation, tooling and infrastructure to streamline testing - Create and test suites of UI applications using our public APIs and not yet released APIs under development. - Work closely with multi-functional organizations, software engineering teams, and QA teams<br> <br> <b>Minimum Qualifications</b><br>\n <ul>\n  <li>2+ Years of experience using Swift or Objective-C in Xcode developing for Apple platforms including automated testing using XCTests &amp; XCUITests.</li>\n  <li>Detail oriented, analytical, curious and creative problem solver with interest in developing high quality software</li>\n  <li>Ability to prioritize work, synthesize results, and escalate issues to the relevant stakeholders</li>\n  <li>BS or MS in CS/CE or equivalent experience</li>\n </ul><br> <b> Preferred Qualifications</b><br>\n <ul>\n  <li>Excellent written and verbal communication skills and ability to work closely with development teams, management, and other organizations within Apple</li>\n  <li>Experience debugging &amp; triaging software issues within a large codebase</li>\n  <li>Experience building, maintaining &amp; deploying automated test suites within a continuous integration system, reporting regressions, tracking regressions &amp; verifying fixes</li>\n  <li>Familiarity with SwiftUI</li>\n </ul><br> <b> Pay &amp; Benefits</b><br>\n <ul>\n  At Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $143,100 and $264,200, and your base pay will depend on your skills, qualifications, experience, and location.  Apple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.  Note: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n </ul><br> More<br>\n <ul>\n  <li>Apple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.</li>\n </ul>\n</div>",
        "descriptionText": "Summary\n\nPosted: Oct 31, 2024\n\nWeekly Hours: 40\n\nRole Number:200576722\n\nThe Swift Platforms Experience team is looking for a driven and dedicated Software Engineer in Test. Our team is responsible for testing and ensuring the quality of major frameworks and tooling including Foundation, UIKit, SwiftUI, Swift Charts and Xcode Previews. You’ll be working directly with the talented Software Engineers and Quality Assurance Engineers responsible for the building blocks of apps across all of Apple’s platforms! Help us build applications, infrastructure, and tooling to validate the quality of our APIs in creative ways. The job responsibilities include: building, scaling, and maintaining XCTests & XCUITests across our projects; testing our framework APIs; and, building validation tools to continuously improve the Quality Engineering Process. To ensure the best developer experience, you will also be responsible for testing framework behavior in our external developer tools such as Xcode Previews. You will be part of a Quality Engineering team that works and collaborates closely with the Engineering teams to create and ship exciting new features across Apple’s platforms. Our ideal candidate has a passion for code quality, continuously learning, facing new challenges, and values the third party developer experience.\n\nDescription\n\n- Gain a deep understanding of the design, requirements and architecture within the Swift Platform Experience frameworks - Devise and execute a testing strategy for features created by the Swift Platform Experience team - Provide functional and integration quality assurance testing for features across all of Apple’s platforms - Explore novel approaches to build or improve test frameworks, automation, tooling and infrastructure to streamline testing - Create and test suites of UI applications using our public APIs and not yet released APIs under development. - Work closely with multi-functional organizations, software engineering teams, and QA teams\n\nMinimum Qualifications\n\n2+ Years of experience using Swift or Objective-C in Xcode developing for Apple platforms including automated testing using XCTests & XCUITests.\nDetail oriented, analytical, curious and creative problem solver with interest in developing high quality software\nAbility to prioritize work, synthesize results, and escalate issues to the relevant stakeholders\nBS or MS in CS/CE or equivalent experience\n\nPreferred Qualifications\n\nExcellent written and verbal communication skills and ability to work closely with development teams, management, and other organizations within Apple\nExperience debugging & triaging software issues within a large codebase\nExperience building, maintaining & deploying automated test suites within a continuous integration system, reporting regressions, tracking regressions & verifying fixes\nFamiliarity with SwiftUI\n\nPay & Benefits\n\nAt Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $143,100 and $264,200, and your base pay will depend on your skills, qualifications, experience, and location.\n\nApple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.\n\nNote: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n\nMore\n\nApple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.",
        "age": "Just posted",
        "datePublished": "2025-01-01T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 264200,
          "salaryMin": 143100,
          "salarySource": "EXTRACTION",
          "salaryText": "$143,100 - $264,200 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "425c23ea1ce8fe95",
        "source": "Apple",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=425c23ea1ce8fe95",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 5
        }
      },
      {
        "title": "DevOps Engineer",
        "jobType": "Full-time",
        "companyName": "Thales",
        "companyUrl": "https://www.indeed.com/cmp/Thales",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/cb7cd4ed538015d391f0f28490b9b08b",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/3765d4d2829f434fb9a05dd723030300",
        "rating": {
          "ariaContent": "3.9 out of 5 stars. Link to 2,771 company reviews (opens in a new tab)",
          "count": 2771,
          "countContent": "2,771 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 3.9,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "San Jose",
          "postalCode": null,
          "latitude": 37.33939,
          "longitude": -121.89496,
          "streetAddress": null,
          "formattedAddressLong": "San Jose, CA",
          "formattedAddressShort": "San Jose, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations",
          "Software Development Operations Occupations"
        ],
        "benefits": [
          "Paid holidays",
          "Health insurance",
          "Dental insurance",
          "Life insurance",
          "Retirement plan",
          "Paid sick time"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "CI/CD",
          "Background check",
          "Computer science",
          "Cloud infrastructure",
          "Go",
          "Computer Science",
          "Ansible",
          "DevOps",
          "Paid holidays",
          "Full-time",
          "Google Cloud Platform",
          "Mid-level",
          "Windows",
          "GitLab CI/CD",
          "Master's degree",
          "Health insurance",
          "Bash",
          "Dental insurance",
          "OS Kernels",
          "AWS",
          "C++",
          "C",
          "Bachelor's degree",
          "JavaScript",
          "Terraform",
          "Computer Engineering",
          "Ubuntu",
          "Scripting",
          "APIs",
          "Puppet",
          "Linux",
          "Monday to Friday",
          "2 years",
          "Jenkins",
          "GitLab",
          "Python",
          "Shell Scripting",
          "Life insurance",
          "Retirement plan",
          "Paid sick time"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 45,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n Location: San Jose, United States of America\n <p></p> Thales people architect identity management and data protection solutions at the heart of digital security. Business and governments rely on us to bring trust to the billons of digital interactions they have with people. Our technologies and services help banks exchange funds, people cross borders, energy become smarter and much more. More than 30,000 organizations already rely on us to verify the identities of people and things, grant access to digital services, analyze vast quantities of information and encrypt data to make the connected world more secure.\n <p></p>\n <div>\n  <p><b> This is a hybrid role in San Jose, CA.</b></p>\n  <p></p>\n  <p><b> Position Summary</b></p>\n </div>\n <p><br> As a DevOps Engineer, you will play a pivotal role in streamlining our software development and deployment processes. You will collaborate closely with development, operations, and quality assurance teams to automate and optimize our infrastructure and workflows. Your expertise in automation tools, cloud technologies, and infrastructure as code will be instrumental in ensuring the efficient delivery of high-quality software. The jobholder will be required to perform hands-on role, taking part in CI/CD, tooling, and automation.</p>\n <p></p>\n <div>\n  <p><b> Key Areas of </b><b>Responsibility </b></p>\n </div>\n <p></p>\n <p>Key Tasks The successful applicant will work within a project system engineering team and have the following responsibilities:</p>\n <ul>\n  <li><p>Infrastructure Automation: Design, implement, and maintain infrastructure as code solutions using tools like Terraform or Ansible to automate provisioning and configuration of servers, networks, and databases.</p></li>\n  <li><p>CI/CD Pipeline Development: Build and maintain robust CI/CD pipelines using tools like Jenkins, GitLab CI/CD to automate the build, test, and deployment processes.</p></li>\n  <li><p>Cloud Platform Management: Manage and optimize our cloud infrastructure on platforms like AWS, Azure, or GCP, ensuring high availability, scalability, and cost-efficiency.</p></li>\n  <li><p>Monitoring and Alerting: Implement monitoring tools like Prometheus, Grafana, or Datadog to track system performance and proactively identify and resolve issues.</p></li>\n  <li><p>Security and Compliance: Adhere to security best practices and implement security measures to protect our infrastructure and applications. Integrate security tools and practices into our CI/CD pipelines to automate security testing and vulnerability scanning.</p></li>\n  <li><p>Collaboration: Work closely with development teams to understand their needs and provide solutions to improve their workflow.</p></li>\n </ul>\n <p></p>\n <div>\n  <p><b> Basic Qualifications</b></p>\n </div>\n <ul>\n  <li><p>2+ years of experience in DevOps</p></li>\n  <li><p>Bachelors / master’s degree in computer science Engineering</p></li>\n  <li><p>Kernel build experience on Windows, RedHat, Ubuntu, SLES, Linux, MSFT driver attestation, Partner Center API scripting</p></li>\n  <li><p>Strong proficiency in scripting languages like C/C++, Python, Golang, Bash, JavaScript, TCL and Expect.</p></li>\n  <li><p>Ability to modify Makefile and analize make issues.</p></li>\n  <li><p>Experience with configuration management tools like Ansible Puppet</p></li>\n </ul>\n <p></p>\n <div>\n  <p><b> Physical Demands</b></p>\n </div>\n <p></p>\n <p>Prolonged periods working on a computer.</p>\n <p></p>\n <p><b> Special Position Requirements</b></p>\n <p>Schedule: Core Business Hours Monday-Friday, etc.<br> Physical Environment: required to be in office with the ability to work hybrid.</p>\n <p><b><br> What We Offer</b></p>\n <p><br> The anticipated TTC range for this role is <i>93,672.60 - 191,878.00 USD</i> Annual. The Company reserves the right to ultimately pay more or less than the posted range and offer additional benefits and other compensation, depending on circumstances not related to an applicant’s status protected by local, state, or federal law.</p>\n <p><br> Thales provides an extensive benefits program for all full-time employees working 30 or more hours per week and their eligible dependents, including the following:</p>\n <p>Elective Health and Dental plans.<br> Retirement Savings Plan with a company contribution and a match, and without vesting period.<br> Company paid holidays, vacation days, and paid sick leave.<br> Company provided Life Insurance.</p>\n <p><b><br> Why Join Us?</b><br> Say HI and learn more about working at Thales <i>click here</i></p>\n <p><br> #LI-WM1<br> #LI-Hybrid</p>\n <p></p> This position will require successfully completing a post-offer background check. Qualified candidates with [a] criminal history will be considered and are not automatically disqualified, consistent with federal law, state law, and local ordinances.\n <p></p>\n <p>Successful applicant must comply with federal contractor vaccine mandate requirements.</p>\n <p></p>\n <p>Thales champions inclusion and we believe diversity strengthens the fabric of our culture. We are an equal opportunity/affirmative action employer. All qualified applicants will receive consideration for employment without regard to sex, gender identity, sexual orientation, race, color, religion, national origin, disability, protected Veteran status, age, or any other characteristic protected by law.</p>\n <p><br> If you need an accommodation or assistance in order to apply for a position with Thales, please contact us at talentacquisition@us.thalesgroup.com.</p>\n</div>\n<p></p>",
        "descriptionText": "Location: San Jose, United States of America\n\nThales people architect identity management and data protection solutions at the heart of digital security. Business and governments rely on us to bring trust to the billons of digital interactions they have with people. Our technologies and services help banks exchange funds, people cross borders, energy become smarter and much more. More than 30,000 organizations already rely on us to verify the identities of people and things, grant access to digital services, analyze vast quantities of information and encrypt data to make the connected world more secure.\n\nThis is a hybrid role in San Jose, CA.\n\nPosition Summary\n\nAs a DevOps Engineer, you will play a pivotal role in streamlining our software development and deployment processes. You will collaborate closely with development, operations, and quality assurance teams to automate and optimize our infrastructure and workflows. Your expertise in automation tools, cloud technologies, and infrastructure as code will be instrumental in ensuring the efficient delivery of high-quality software. The jobholder will be required to perform hands-on role, taking part in CI/CD, tooling, and automation.\n\nKey Areas of Responsibility\n\nKey Tasks The successful applicant will work within a project system engineering team and have the following responsibilities:\n\nInfrastructure Automation: Design, implement, and maintain infrastructure as code solutions using tools like Terraform or Ansible to automate provisioning and configuration of servers, networks, and databases.\n\nCI/CD Pipeline Development: Build and maintain robust CI/CD pipelines using tools like Jenkins, GitLab CI/CD to automate the build, test, and deployment processes.\n\nCloud Platform Management: Manage and optimize our cloud infrastructure on platforms like AWS, Azure, or GCP, ensuring high availability, scalability, and cost-efficiency.\n\nMonitoring and Alerting: Implement monitoring tools like Prometheus, Grafana, or Datadog to track system performance and proactively identify and resolve issues.\n\nSecurity and Compliance: Adhere to security best practices and implement security measures to protect our infrastructure and applications. Integrate security tools and practices into our CI/CD pipelines to automate security testing and vulnerability scanning.\n\nCollaboration: Work closely with development teams to understand their needs and provide solutions to improve their workflow.\n\nBasic Qualifications\n\n2+ years of experience in DevOps\n\nBachelors / master’s degree in computer science Engineering\n\nKernel build experience on Windows, RedHat, Ubuntu, SLES, Linux, MSFT driver attestation, Partner Center API scripting\n\nStrong proficiency in scripting languages like C/C++, Python, Golang, Bash, JavaScript, TCL and Expect.\n\nAbility to modify Makefile and analize make issues.\n\nExperience with configuration management tools like Ansible Puppet\n\nPhysical Demands\n\nProlonged periods working on a computer.\n\nSpecial Position Requirements\n\nSchedule: Core Business Hours Monday-Friday, etc.\nPhysical Environment: required to be in office with the ability to work hybrid.\n\nWhat We Offer\n\nThe anticipated TTC range for this role is 93,672.60 - 191,878.00 USD Annual. The Company reserves the right to ultimately pay more or less than the posted range and offer additional benefits and other compensation, depending on circumstances not related to an applicant’s status protected by local, state, or federal law.\n\nThales provides an extensive benefits program for all full-time employees working 30 or more hours per week and their eligible dependents, including the following:\n\nElective Health and Dental plans.\nRetirement Savings Plan with a company contribution and a match, and without vesting period.\nCompany paid holidays, vacation days, and paid sick leave.\nCompany provided Life Insurance.\n\nWhy Join Us?\nSay HI and learn more about working at Thales click here\n\n#LI-WM1\n#LI-Hybrid\n\nThis position will require successfully completing a post-offer background check. Qualified candidates with [a] criminal history will be considered and are not automatically disqualified, consistent with federal law, state law, and local ordinances.\n\nSuccessful applicant must comply with federal contractor vaccine mandate requirements.\n\nThales champions inclusion and we believe diversity strengthens the fabric of our culture. We are an equal opportunity/affirmative action employer. All qualified applicants will receive consideration for employment without regard to sex, gender identity, sexual orientation, race, color, religion, national origin, disability, protected Veteran status, age, or any other characteristic protected by law.\n\nIf you need an accommodation or assistance in order to apply for a position with Thales, please contact us at talentacquisition@us.thalesgroup.com.",
        "age": "1 day ago",
        "datePublished": "2024-12-30T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 191878,
          "salaryMin": 93672.6,
          "salarySource": "EXTRACTION",
          "salaryText": "$93,672.60 - $191,878.00 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "b14fc169df64b1f4",
        "source": "Thales",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=b14fc169df64b1f4",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 6
        }
      },
      {
        "title": "Software Engineering PMTS",
        "jobType": "Full-time",
        "companyName": "Salesforce",
        "companyUrl": "https://www.indeed.com/cmp/Salesforce",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/581b81cad76664246c42f85c30523dd2",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/92e7f19a69c7e7252ff1acbe1c5f0c7a",
        "rating": {
          "ariaContent": "4.2 out of 5 stars. Link to 1,246 company reviews (opens in a new tab)",
          "count": 1246,
          "countContent": "1,246 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.2,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "San Francisco",
          "postalCode": "94105",
          "latitude": 37.789764,
          "longitude": -122.3969,
          "streetAddress": "415 Mission Street, 3rd Floor",
          "formattedAddressLong": "San Francisco, CA 94105",
          "formattedAddressShort": "San Francisco, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [],
        "socialInsurance": [],
        "workingSystem": [],
        "attributes": [
          "Cloud infrastructure",
          "Go",
          "Cloud architecture",
          "Kubernetes",
          "System design",
          "Full-time",
          "Google Cloud Platform",
          "Java",
          "8 years",
          "Microservices",
          "Statistical analysis",
          "Analysis skills",
          "Distributed systems",
          "Mentoring",
          "Ruby",
          "Fair chance",
          "Agile",
          "Cloud computing",
          "Senior level",
          "AI",
          "Communication skills",
          "Python",
          "SDLC",
          "Design patterns"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 5,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <p><i>To get the best candidate experience, please consider applying for a maximum of 3 roles within 12 months to ensure you are not duplicating efforts. </i></p>\n <p></p>\n <p>Job Category</p>Software Engineering \n <p></p>\n <p>Job Details</p>\n <p></p>\n <p><b>About Salesforce </b></p>\n <p>We’re Salesforce, the Customer Company, inspiring the future of business with AI+ Data +CRM. Leading with our core values, we help companies across every industry blaze new trails and connect with customers in a whole new way. And, we empower you to be a Trailblazer, too — driving your performance and career growth, charting new paths, and improving the state of the world. If you believe in business as the greatest platform for change and in companies doing well and doing good – you’ve come to the right place.</p>\n <p></p>\n <p>We are seeking a highly skilled, expert Infrastructure Software Engineer join our team! The ideal candidate will have a strong background in software engineering, with significant experience in system design, distributed systems and AI / ML. This role involves working closely with a diverse team of engineers to design, implement, and review software solutions to automate compute and network infrastructure lifecycle operations at scale across Salesforce’s physical data center footprint. This role will also contribute to the development of a comprehensive infrastructure health and change safety platform tasked with ensuring rapid detection of service/infrastructure fabric performance degradation and root cause analysis in Salesforce’s cloud infrastructure environments. If you are adept at designing and implementing large scale, low latency, critically important software systems and thrive in a collaborative, multi-cultural environment, we invite you to join our team!</p>\n <p></p>\n <h3 class=\"jobSectionHeader\"><b>Key Responsibilities: </b></h3>\n <ul>\n  <li>Develop resilient closed loop infrastructure automation and change safety platforms/features to ensure our customers experience the highest levels of availability.</li>\n  <li>Lead design and implementation of services/features with a focus on scalability, reliability, and maintainability.</li>\n  <li>Translate business vision and architecture into well-engineered solutions that best leverage our platforms and products.</li>\n  <li>Develop and implement distributed systems, ensuring alignment with business objectives and architectural north star.</li>\n  <li>Mentor and provide technical leadership to the junior members of the engineering team.</li>\n  <li>Fix and resolve sophisticated technical issues.</li>\n </ul>\n <p></p>\n <h3 class=\"jobSectionHeader\"><b>Required Qualifications: </b></h3>\n <ul>\n  <li>Minimum of 8 years of proven experience as a Software Engineer, with a focus on system design and distributed systems.</li>\n  <li>Strong experience with modern software architectural principles and distributed system design patterns.</li>\n  <li>Experience with cloud computing platforms (e.g., AWS, Azure, GCP) and container orchestration (e.g., Kubernetes).</li>\n  <li>Experience in building and managing systems integrations, data processing pipelines, and fault tolerant distributed systems.</li>\n  <li>Deep knowledge of programming and technical fluency with at least one of the following programming languages: Golang, Java, Ruby, Python</li>\n  <li>Excellent understanding of the software development life cycle and agile methodologies.</li>\n  <li>Strong problem-solving and analytical skills.</li>\n  <li>Experience mentoring and influencing the contributions of junior engineers.</li>\n  <li>Excellent communication and interpersonal skills, with the ability to articulate complex technical concepts and lead design reviews.</li>\n </ul>\n <h3 class=\"jobSectionHeader\"><b>Preferred Qualifications: </b></h3>\n <ul>\n  <li>Experience with cloud technologies and microservices architecture.</li>\n  <li>Prior experience with AI/ML and/or statistical analysis models to inform production automation at scale.</li>\n  <li>Ability to evaluate a problem space and make a technology decision based on what’s best for the customer.</li>\n  <li>Contributions to open-source projects or a strong portfolio of original projects.</li>\n </ul>\n <h3 class=\"jobSectionHeader\">\n  <ul>\n   <li><b>LI-Y </b></li>\n  </ul><p></p><p><b>Accommodations </b></p><p><b>If you require assistance due to a disability applying for open positions please submit a request via this </b><b>Accommodations Request Form </b><b>. </b></p><p></p><p><b>Posting Statement </b></p><p><b>At Salesforce we believe that the business of business is to improve the state of our world. Each of us has a responsibility to drive Equality in our communities and workplaces. We are committed to creating a workforce that reflects society through inclusive programs and initiatives such as equal pay, employee resource groups, inclusive benefits, and more. Learn more about Equality at </b><b>www.equality.com </b><b>and explore our company benefits at </b><b>www.salesforcebenefits.com </b><b>. </b></p><p></p><p><b>Salesforce </b><b>is an Equal Employment Opportunity and Affirmative Action Employer. Qualified applicants will receive consideration for employment without regard to race, color, religion, sex, sexual orientation, gender perception or identity, national origin, age, marital status, protected veteran status, or disability status. </b><b>Salesforce </b><b>does not accept unsolicited headhunter and agency resumes. </b><b>Salesforce </b><b>will not pay any third-party agency or company that does not have a signed agreement with </b><b>Salesforce </b><b>. ﻿</b></p><p></p><p><b>Salesforce welcomes all. </b></p><p></p><b>Pursuant to the San Francisco Fair Chance Ordinance and the Los Angeles Fair Chance Initiative for Hiring, Salesforce will consider for employment qualified applicants with arrest and conviction records. </b></h3>\n <p></p>\n <h3 class=\"jobSectionHeader\"><b>For Washington-based roles, the base salary hiring range for this position is $184,000 to $306,600. </b></h3>\n <p></p>\n <h3 class=\"jobSectionHeader\"><b>For California-based roles, the base salary hiring range for this position is $200,800 to $334,600. </b></h3>\n <p></p>\n <h3 class=\"jobSectionHeader\"><b>Compensation offered will be determined by factors such as location, level, job-related knowledge, skills, and experience. Certain roles may be eligible for incentive compensation, equity, benefits. More details about our company benefits can be found at the following link: https://www.salesforcebenefits.com.</b></h3>\n</div>",
        "descriptionText": "To get the best candidate experience, please consider applying for a maximum of 3 roles within 12 months to ensure you are not duplicating efforts.\n\nJob Category\n\nSoftware Engineering\n\nJob Details\n\nAbout Salesforce\n\nWe’re Salesforce, the Customer Company, inspiring the future of business with AI+ Data +CRM. Leading with our core values, we help companies across every industry blaze new trails and connect with customers in a whole new way. And, we empower you to be a Trailblazer, too — driving your performance and career growth, charting new paths, and improving the state of the world. If you believe in business as the greatest platform for change and in companies doing well and doing good – you’ve come to the right place.\n\nWe are seeking a highly skilled, expert Infrastructure Software Engineer join our team! The ideal candidate will have a strong background in software engineering, with significant experience in system design, distributed systems and AI / ML. This role involves working closely with a diverse team of engineers to design, implement, and review software solutions to automate compute and network infrastructure lifecycle operations at scale across Salesforce’s physical data center footprint. This role will also contribute to the development of a comprehensive infrastructure health and change safety platform tasked with ensuring rapid detection of service/infrastructure fabric performance degradation and root cause analysis in Salesforce’s cloud infrastructure environments. If you are adept at designing and implementing large scale, low latency, critically important software systems and thrive in a collaborative, multi-cultural environment, we invite you to join our team!\n\nKey Responsibilities:\nDevelop resilient closed loop infrastructure automation and change safety platforms/features to ensure our customers experience the highest levels of availability.\nLead design and implementation of services/features with a focus on scalability, reliability, and maintainability.\nTranslate business vision and architecture into well-engineered solutions that best leverage our platforms and products.\nDevelop and implement distributed systems, ensuring alignment with business objectives and architectural north star.\nMentor and provide technical leadership to the junior members of the engineering team.\nFix and resolve sophisticated technical issues.\n\nRequired Qualifications:\nMinimum of 8 years of proven experience as a Software Engineer, with a focus on system design and distributed systems.\nStrong experience with modern software architectural principles and distributed system design patterns.\nExperience with cloud computing platforms (e.g., AWS, Azure, GCP) and container orchestration (e.g., Kubernetes).\nExperience in building and managing systems integrations, data processing pipelines, and fault tolerant distributed systems.\nDeep knowledge of programming and technical fluency with at least one of the following programming languages: Golang, Java, Ruby, Python\nExcellent understanding of the software development life cycle and agile methodologies.\nStrong problem-solving and analytical skills.\nExperience mentoring and influencing the contributions of junior engineers.\nExcellent communication and interpersonal skills, with the ability to articulate complex technical concepts and lead design reviews.\nPreferred Qualifications:\nExperience with cloud technologies and microservices architecture.\nPrior experience with AI/ML and/or statistical analysis models to inform production automation at scale.\nAbility to evaluate a problem space and make a technology decision based on what’s best for the customer.\nContributions to open-source projects or a strong portfolio of original projects.\n\n*LI-Y\n\nAccommodations\n\nIf you require assistance due to a disability applying for open positions please submit a request via this Accommodations Request Form .\n\nPosting Statement\n\nAt Salesforce we believe that the business of business is to improve the state of our world. Each of us has a responsibility to drive Equality in our communities and workplaces. We are committed to creating a workforce that reflects society through inclusive programs and initiatives such as equal pay, employee resource groups, inclusive benefits, and more. Learn more about Equality at www.equality.com and explore our company benefits at www.salesforcebenefits.com .\n\nSalesforce is an Equal Employment Opportunity and Affirmative Action Employer. Qualified applicants will receive consideration for employment without regard to race, color, religion, sex, sexual orientation, gender perception or identity, national origin, age, marital status, protected veteran status, or disability status. Salesforce does not accept unsolicited headhunter and agency resumes. Salesforce will not pay any third-party agency or company that does not have a signed agreement with Salesforce .\n\n﻿Salesforce welcomes all.\n\nPursuant to the San Francisco Fair Chance Ordinance and the Los Angeles Fair Chance Initiative for Hiring, Salesforce will consider for employment qualified applicants with arrest and conviction records.\n\nFor Washington-based roles, the base salary hiring range for this position is $184,000 to $306,600.\n\nFor California-based roles, the base salary hiring range for this position is $200,800 to $334,600.\n\nCompensation offered will be determined by factors such as location, level, job-related knowledge, skills, and experience. Certain roles may be eligible for incentive compensation, equity, benefits. More details about our company benefits can be found at the following link: https://www.salesforcebenefits.com.",
        "age": "1 day ago",
        "datePublished": "2024-12-30T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 334600,
          "salaryMin": 184000,
          "salarySource": "EXTRACTION",
          "salaryText": "$184,000 - $334,600 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "5367d8d17e762551",
        "source": "Salesforce",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=5367d8d17e762551",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 7
        }
      },
      {
        "title": "Site Reliability Engineer",
        "jobType": "Full-time",
        "companyName": "JPMorganChase",
        "companyUrl": "https://www.indeed.com/cmp/Jpmorganchase-2",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/62e186e96c7550325814ef6880fae379",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/e5f2926890cd9374a94016d6281c3e40",
        "rating": {
          "ariaContent": "3.9 out of 5 stars. Link to 19,749 company reviews (opens in a new tab)",
          "count": 19749,
          "countContent": "19,749 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 3.9,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Palo Alto",
          "postalCode": "94304",
          "latitude": 37.41298,
          "longitude": -122.14265,
          "streetAddress": "3223 Hanover Street",
          "formattedAddressLong": "Palo Alto, CA 94304",
          "formattedAddressShort": "Palo Alto, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations",
          "Software Development Operations Occupations"
        ],
        "benefits": [
          "Health insurance",
          "Tuition reimbursement",
          "Retirement plan"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "Commission pay",
          "TCP",
          "Computer Science",
          "Software Engineering",
          "DevOps",
          "Full-time",
          "Git",
          "3 years",
          "Master's degree",
          "Health insurance",
          "AWS",
          "Bachelor's degree",
          "Tuition reimbursement",
          "SRE",
          "Linux",
          "HTTPS",
          "Senior level",
          "On call",
          "Jenkins",
          "Python",
          "Shell Scripting",
          "Retirement plan",
          "SDLC",
          "Information Technology"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 15,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <b>JOB DESCRIPTION</b>\n <p><br> DESCRIPTION:</p>\n <p>Duties: Implement SRE frameworks to support globally multi-cloud environments. Failure analysis/root cause analysis. Develop technical engineering documentation. Drive software development lifecycle maturity. Quality control. Technical consultation. Perform deployment, administration, management, configuration, testing, and integration. Develop new cloud engineering strategies and implementations. Champion an automated DevOps model. Coaching and mentoring junior team members. Write operation documentation and knowledge base of known issues with solutions. Perform 24x7 SRE on-call rotations and escalation workflows.</p>\n <p><br> QUALIFICATIONS:</p>\n <p>Minimum education and experience required: Master’s degree in Software Engineering, Information Technology, or related field of study plus 3 years of experience in the job offered or as a Site Reliability Engineer, Member of Technical Staff, Automation Engineer, System Architect, or related occupation. The employer will alternatively accept a Bachelor's degree in Software Engineering, Information Technology, or related field of study plus 5 years of experience in the job offered or as a Site Reliability Engineer, Member of Technical Staff, Automation Engineer, System Architect, or related occupation.</p>\n <p>Skills Required: Requires experience in the following: Git; Prometheus; Shell Scripting; Infrastructure as Code; AWS Cloud Computing; Jenkins; Grafana; Linux; Python; Networking; HTTPS; TCP; and UDP.</p>\n <p>Job Location: 3223 Hanover St, Palo Alto, CA 94304.Telecommuting permitted up to 40% of the week.</p>\n <p>Full-Time. Salary: $226,158 - $226,158 per year.</p> <b>ABOUT US</b><br>\n <div>\n  <div>\n   JPMorganChase, one of the oldest financial institutions, offers innovative financial solutions to millions of consumers, small businesses and many of the world’s most prominent corporate, institutional and government clients under the J.P. Morgan and Chase brands. Our history spans over 200 years and today we are a leader in investment banking, consumer and small business banking, commercial banking, financial transaction processing and asset management.\n  </div>\n  <p></p>\n  <div>\n   <p>We offer a competitive total rewards package including base salary determined based on the role, experience, skill set and location. Those in eligible roles may receive commission-based pay and/or discretionary incentive compensation, paid in the form of cash and/or forfeitable equity, awarded in recognition of individual achievements and contributions. We also offer a range of benefits and programs to meet employee needs, based on eligibility. These benefits include comprehensive health care coverage, on-site health and wellness centers, a retirement savings plan, backup childcare, tuition reimbursement, mental health support, financial coaching and more. Additional details about total compensation and benefits will be provided during the hiring process.</p>\n   <div>\n    <p>We recognize that our people are our strength and the diverse talents they bring to our global workforce are directly linked to our success. We are an equal opportunity employer and place a high value on diversity and inclusion at our company. We do not discriminate on the basis of any protected attribute, including race, religion, color, national origin, gender, sexual orientation, gender identity, gender expression, age, marital or veteran status, pregnancy or disability, or any other basis protected under applicable law. We also make reasonable accommodations for applicants’ and employees’ religious practices and beliefs, as well as mental health or physical disability needs. Visit our FAQs for more information about requesting an accommodation.</p>\n    <p>JPMorgan Chase &amp; Co. is an Equal Opportunity Employer, including Disability/Veterans</p><br>\n   </div>\n  </div>\n </div><br> <br> <b>ABOUT THE TEAM</b><br> <br> Our professionals in our Corporate Functions cover a diverse range of areas from finance and risk to human resources and marketing. Our corporate teams are an essential part of our company, ensuring that we’re setting our businesses, clients, customers and employees up for success.\n</div>",
        "descriptionText": "JOB DESCRIPTION\n\nDESCRIPTION:\n\nDuties: Implement SRE frameworks to support globally multi-cloud environments. Failure analysis/root cause analysis. Develop technical engineering documentation. Drive software development lifecycle maturity. Quality control. Technical consultation. Perform deployment, administration, management, configuration, testing, and integration. Develop new cloud engineering strategies and implementations. Champion an automated DevOps model. Coaching and mentoring junior team members. Write operation documentation and knowledge base of known issues with solutions. Perform 24x7 SRE on-call rotations and escalation workflows.\n\nQUALIFICATIONS:\n\nMinimum education and experience required: Master’s degree in Software Engineering, Information Technology, or related field of study plus 3 years of experience in the job offered or as a Site Reliability Engineer, Member of Technical Staff, Automation Engineer, System Architect, or related occupation. The employer will alternatively accept a Bachelor's degree in Software Engineering, Information Technology, or related field of study plus 5 years of experience in the job offered or as a Site Reliability Engineer, Member of Technical Staff, Automation Engineer, System Architect, or related occupation.\n\nSkills Required: Requires experience in the following: Git; Prometheus; Shell Scripting; Infrastructure as Code; AWS Cloud Computing; Jenkins; Grafana; Linux; Python; Networking; HTTPS; TCP; and UDP.\n\nJob Location: 3223 Hanover St, Palo Alto, CA 94304.Telecommuting permitted up to 40% of the week.\n\nFull-Time. Salary: $226,158 - $226,158 per year.\n\nABOUT US\n\nJPMorganChase, one of the oldest financial institutions, offers innovative financial solutions to millions of consumers, small businesses and many of the world’s most prominent corporate, institutional and government clients under the J.P. Morgan and Chase brands. Our history spans over 200 years and today we are a leader in investment banking, consumer and small business banking, commercial banking, financial transaction processing and asset management.\n\nWe offer a competitive total rewards package including base salary determined based on the role, experience, skill set and location. Those in eligible roles may receive commission-based pay and/or discretionary incentive compensation, paid in the form of cash and/or forfeitable equity, awarded in recognition of individual achievements and contributions. We also offer a range of benefits and programs to meet employee needs, based on eligibility. These benefits include comprehensive health care coverage, on-site health and wellness centers, a retirement savings plan, backup childcare, tuition reimbursement, mental health support, financial coaching and more. Additional details about total compensation and benefits will be provided during the hiring process.\n\nWe recognize that our people are our strength and the diverse talents they bring to our global workforce are directly linked to our success. We are an equal opportunity employer and place a high value on diversity and inclusion at our company. We do not discriminate on the basis of any protected attribute, including race, religion, color, national origin, gender, sexual orientation, gender identity, gender expression, age, marital or veteran status, pregnancy or disability, or any other basis protected under applicable law. We also make reasonable accommodations for applicants’ and employees’ religious practices and beliefs, as well as mental health or physical disability needs. Visit our FAQs for more information about requesting an accommodation.\n\nJPMorgan Chase & Co. is an Equal Opportunity Employer, including Disability/Veterans\n\nABOUT THE TEAM\n\nOur professionals in our Corporate Functions cover a diverse range of areas from finance and risk to human resources and marketing. Our corporate teams are an essential part of our company, ensuring that we’re setting our businesses, clients, customers and employees up for success.",
        "age": "1 day ago",
        "datePublished": "2024-12-31T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 226158,
          "salaryMin": 226158,
          "salarySource": "EXTRACTION",
          "salaryText": "$226,158 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "e241bc7a53c5a599",
        "source": "JPMorgan Chase",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=e241bc7a53c5a599",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 8
        }
      },
      {
        "title": "Full Stack Developer, Software Engineer",
        "jobType": "Full-time",
        "companyName": "Adobe",
        "companyUrl": "https://www.indeed.com/cmp/Adobe",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/8556eb9d8fef8a256b09c6eed07eb084",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/8723ab138c64f79f6bbba5e276ca85f5",
        "rating": {
          "ariaContent": "4.3 out of 5 stars. Link to 844 company reviews (opens in a new tab)",
          "count": 844,
          "countContent": "844 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.3,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "San Jose",
          "postalCode": "95110",
          "latitude": 37.336533,
          "longitude": -121.89953,
          "streetAddress": null,
          "formattedAddressLong": "San Jose, CA 95110",
          "formattedAddressShort": "San Jose, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [],
        "socialInsurance": [],
        "workingSystem": [],
        "attributes": [
          "Commission pay",
          "Node.js",
          "Computer Science",
          "Bachelor of Science",
          "Data structures",
          "System design",
          "Full-time",
          "Mid-level",
          "3 years",
          "Algorithms",
          "Microservices",
          "PHP",
          "OOP",
          "AWS",
          "Docker",
          "Bachelor's degree",
          "JavaScript",
          "Distributed systems",
          "Splunk",
          "ECMAScript",
          "New Relic",
          "Fair chance",
          "Agile",
          "GraphQL",
          "TypeScript"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 145,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "Our Company <br><br> Changing the world through digital experiences is what Adobe’s all about. We give everyone—from emerging artists to global brands—everything they need to design and deliver exceptional digital experiences! We’re passionate about empowering people to create beautiful and powerful images, videos, and apps, and transform how companies interact with customers across every screen. <br><br> We’re on a mission to hire the very best and are committed to creating exceptional employee experiences where everyone is respected and has access to equal opportunity. We realize that new ideas can come from everywhere in the organization, and we know the next big idea could be yours! <br><br> What you'll do <br>You’ll be working as part of a team, crafting innovative new features and maintaining existing ones for Adobe Stock using extraordinary technologies. This team focuses on building and supporting highly scalable libraries and middleware for the Adobe Stock ecosystem. The ideal candidate will need a keen eye for detail, high code quality, and efficiency standards. You'll also be expected to debug issues across multiple systems, regularly share knowledge with peers, and contribute to architectural design discussions. Candidates who enjoy tackling sophisticated technical challenges have a passion for delighting customers and are self-motivated to push themselves in a team-oriented culture will thrive in our environment. <br>Keys to your success <br><br> 3+ years of proven experience in developing highly scalable backend services to drive impactful solutions <br><br> B.S. in Computer Science or a related field to apply fundamental principles to complex problems. <br><br> Proficiency in JavaScript and comfortable with ES6, &amp; Express <br><br> Experience building microservices in Node.js, Typescript, and/or PHP to create modular and maintainable systems. <br><br> Implement sophisticated JavaScript techniques such as modules, async/await, compiling and bundling, and server rendering to enhance performance and maintainability. <br><br> Experience in building and maintaining services using GraphQL, with a strong understanding of GraphQL federation to ensure seamless data integration. <br><br> Experience maintaining highly available, fault-tolerant, and distributed services, including familiarity with technologies and architectures like microservices, managed services, AWS, Docker, New Relic, and Splunk. <br><br> Apply computer science principles to real-world problems, applying knowledge of algorithms, data structures, distributed systems, and data flow and storage <br><br> Navigate ambiguous problems and discuss tradeoffs in system design to make informed decisions. <br><br> Strong familiarity with both functional and object-oriented programming to write clean and efficient code. <br><br> Adopt development practices that prioritize robust and reliable software, including writing your own unit tests and integration tests. <br><br> Thrive in an Agile development environment, contributing to iterative and incremental improvements. <br><br> Exhibit a passion for learning new things, working hard, and having fun while doing it. <br>Our compensation reflects the cost of labor across several U.S. geographic markets, and we pay differently based on those defined markets. The U.S. pay range for this position is $113,400 -- $206,300 annually. Pay within this range varies by work location and may also depend on job-related knowledge, skills, and experience. Your recruiter can share more about the specific salary range for the job location during the hiring process. <br><br> At Adobe, for sales roles starting salaries are expressed as total target compensation (TTC = base + commission), and short-term incentives are in the form of sales commission plans. Non-sales roles starting salaries are expressed as base salary and short-term incentives are in the form of the Annual Incentive Plan (AIP). <br><br> In addition, certain roles may be eligible for long-term incentives in the form of a new hire equity award. <br><br> Adobe will consider qualified applicants with arrest or conviction records for employment in accordance with state and local laws and “fair chance” ordinances. <br><br> Adobe is proud to be an Equal Employment Opportunity and affirmative action employer. We do not discriminate based on gender, race or color, ethnicity or national origin, age, disability, religion, sexual orientation, gender identity or expression, veteran status, or any other applicable characteristics protected by law. Learn more. <br><br> Adobe aims to make Adobe.com accessible to any and all users. If you have a disability or special need that requires accommodation to navigate our website or complete the application process, email accommodations@adobe.com or call (408) 536-3015. <br><br> Adobe values a free and open marketplace for all employees and has policies in place to ensure that we do not enter into illegal agreements with other companies to not recruit or hire each other’s employees.",
        "descriptionText": "Our Company\n\nChanging the world through digital experiences is what Adobe’s all about. We give everyone—from emerging artists to global brands—everything they need to design and deliver exceptional digital experiences! We’re passionate about empowering people to create beautiful and powerful images, videos, and apps, and transform how companies interact with customers across every screen.\n\nWe’re on a mission to hire the very best and are committed to creating exceptional employee experiences where everyone is respected and has access to equal opportunity. We realize that new ideas can come from everywhere in the organization, and we know the next big idea could be yours!\n\nWhat you'll do\nYou’ll be working as part of a team, crafting innovative new features and maintaining existing ones for Adobe Stock using extraordinary technologies. This team focuses on building and supporting highly scalable libraries and middleware for the Adobe Stock ecosystem. The ideal candidate will need a keen eye for detail, high code quality, and efficiency standards. You'll also be expected to debug issues across multiple systems, regularly share knowledge with peers, and contribute to architectural design discussions. Candidates who enjoy tackling sophisticated technical challenges have a passion for delighting customers and are self-motivated to push themselves in a team-oriented culture will thrive in our environment.\nKeys to your success\n\n3+ years of proven experience in developing highly scalable backend services to drive impactful solutions\n\nB.S. in Computer Science or a related field to apply fundamental principles to complex problems.\n\nProficiency in JavaScript and comfortable with ES6, & Express\n\nExperience building microservices in Node.js, Typescript, and/or PHP to create modular and maintainable systems.\n\nImplement sophisticated JavaScript techniques such as modules, async/await, compiling and bundling, and server rendering to enhance performance and maintainability.\n\nExperience in building and maintaining services using GraphQL, with a strong understanding of GraphQL federation to ensure seamless data integration.\n\nExperience maintaining highly available, fault-tolerant, and distributed services, including familiarity with technologies and architectures like microservices, managed services, AWS, Docker, New Relic, and Splunk.\n\nApply computer science principles to real-world problems, applying knowledge of algorithms, data structures, distributed systems, and data flow and storage\n\nNavigate ambiguous problems and discuss tradeoffs in system design to make informed decisions.\n\nStrong familiarity with both functional and object-oriented programming to write clean and efficient code.\n\nAdopt development practices that prioritize robust and reliable software, including writing your own unit tests and integration tests.\n\nThrive in an Agile development environment, contributing to iterative and incremental improvements.\n\nExhibit a passion for learning new things, working hard, and having fun while doing it.\nOur compensation reflects the cost of labor across several U.S. geographic markets, and we pay differently based on those defined markets. The U.S. pay range for this position is $113,400 -- $206,300 annually. Pay within this range varies by work location and may also depend on job-related knowledge, skills, and experience. Your recruiter can share more about the specific salary range for the job location during the hiring process.\n\nAt Adobe, for sales roles starting salaries are expressed as total target compensation (TTC = base + commission), and short-term incentives are in the form of sales commission plans. Non-sales roles starting salaries are expressed as base salary and short-term incentives are in the form of the Annual Incentive Plan (AIP).\n\nIn addition, certain roles may be eligible for long-term incentives in the form of a new hire equity award.\n\nAdobe will consider qualified applicants with arrest or conviction records for employment in accordance with state and local laws and “fair chance” ordinances.\n\nAdobe is proud to be an Equal Employment Opportunity and affirmative action employer. We do not discriminate based on gender, race or color, ethnicity or national origin, age, disability, religion, sexual orientation, gender identity or expression, veteran status, or any other applicable characteristics protected by law. Learn more.\n\nAdobe aims to make Adobe.com accessible to any and all users. If you have a disability or special need that requires accommodation to navigate our website or complete the application process, email accommodations@adobe.com or call (408) 536-3015.\n\nAdobe values a free and open marketplace for all employees and has policies in place to ensure that we do not enter into illegal agreements with other companies to not recruit or hire each other’s employees.",
        "age": "6 days ago",
        "datePublished": "2024-12-26T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 206300,
          "salaryMin": 113400,
          "salarySource": "EXTRACTION",
          "salaryText": "$113,400 - $206,300 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "2d6355a851463dd0",
        "source": "Adobe",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=2d6355a851463dd0",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 9
        }
      },
      {
        "title": "Software Engineer, GPU",
        "jobType": "Full-time",
        "companyName": "Waymo",
        "companyUrl": "https://www.indeed.com/cmp/Waymo",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/cddbdd119c56d82802760fa01c0ddb9c",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/95ed4704d9ad44c3eb13160809cdc9da",
        "rating": {
          "ariaContent": "3.1 out of 5 stars. Link to 56 company reviews (opens in a new tab)",
          "count": 56,
          "countContent": "56 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 3.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Mountain View",
          "postalCode": null,
          "latitude": 37.38605,
          "longitude": -122.08385,
          "streetAddress": null,
          "formattedAddressLong": "Mountain View, CA",
          "formattedAddressShort": "Mountain View, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Embedded Software & Firmware Developers",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [],
        "socialInsurance": [],
        "workingSystem": [],
        "attributes": [
          "GPU programming",
          "Computer science",
          "Operating systems",
          "GPU architecture",
          "Computer Science",
          "5 years",
          "Yearly bonus",
          "Full-time",
          "Research",
          "Analysis skills",
          "C++",
          "Embedded software",
          "Bonus opportunities",
          "Hybrid work",
          "Experience equivalent to degree accepted",
          "Senior level",
          "Machine learning frameworks"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 60,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<p>MOUNTAIN VIEW, CALIFORNIA, UNITED STATES. NEW YORK CITY, NEW YORK, UNITED STATES FULL-TIME SOFTWARE ENGINEERING 3235</p> <br>\n<p></p>\n<div>\n <div>\n  <div>\n   <div>\n    <div>\n     <p>Waymo is an autonomous driving technology company with the mission to be the most trusted driver. Since its start as the Google Self-Driving Car Project in 2009, Waymo has focused on building the Waymo Driver—The World's Most Experienced Driver™—to improve access to mobility while saving thousands of lives now lost to traffic crashes. The Waymo Driver powers Waymo One, a fully autonomous ride-hailing service, and can also be applied to a range of vehicle platforms and product use cases. The Waymo Driver has provided over one million rider-only trips, enabled by its experience autonomously driving tens of millions of miles on public roads and tens of billions in simulation across 13+ U.S. states.</p>\n    </div>\n    <p>Waymo's Compute Team is tasked with a critical and exciting mission: We deliver the compute platform responsible for running the completely autonomous vehicle's software stack. To achieve our mission, we architect and create high-performance custom silicon; we develop system-level compute architectures that push the boundaries of performance, power, and latency; and we collaborate with many other teammates to ensure we design and improve hardware and software for maximum performance.</p>\n    <p>In this hybrid role, you will report to a Senior Staff Engineer.</p>\n    <p><b> You will:</b></p>\n    <ul>\n     <li>Collaborate with application teams to understand how to map newly developed and algorithms to GPU, allowing our cars to \"see\" further, operate smarter, and react faster</li>\n     <li>Build primitives and abstractions that allow for scaling our code-base to constantly evolving workloads and hardware</li>\n     <li>Improve and add new compiler optimizations to promote producing optimized GPU assembly</li>\n     <li>Analyze performance counters, GPU micro-architectural features, and algorithms to identify optimization opportunities</li>\n     <li>Contribute to infrastructure that performs testing / static analysis to catch bugs early and create automated alerts to encourage following best GPU performance practices</li>\n     <li>Co-design hardware features and evaluate trade-offs for future generations of our compute platform</li>\n    </ul>\n    <p><b>You have:</b></p>\n    <ul>\n     <li>5+ years experience C++ programming skills</li>\n     <li>Advanced degree in Computer Science, similar technical field of study, or equivalent practical experience</li>\n     <li>5+ years experience with GPU programming / optimization using CUDA or similar technologies</li>\n     <li>1+ years experience with GPU architecture / programming model</li>\n     <li>5+ years experience using performance analysis tools and debuggers</li>\n     <li>5+ years experience with parallel computing/programming</li>\n    </ul>\n    <p><b>We prefer:</b></p>\n    <ul>\n     <li>Experience with LLVM or SPIR-V open-source ecosystems or other compiler projects</li>\n     <li>Operating systems or embedded software experience especially working on device drivers</li>\n     <li>Experience with GPU optimization techniques: memory coalescing, register/shared memory tiling, pinned memory, and warp-level programming</li>\n     <li>Experience with GPU libraries: CUB, CUTLASS, Thrust, or Eigen</li>\n     <li>Research experience in parallel algorithms, compilers, or computer architecture</li>\n     <li>Experience with graphics workloads and shader programming</li>\n     <li>ML frameworks/compiler/library</li>\n    </ul>\n    <p>#LI-Hybrid</p>\n    <div>\n     <div>\n      <div>\n       <p>The expected base salary range for this full-time position across US locations is listed below. Actual starting pay will be based on job-related factors, including exact work location, experience, relevant training and education, and skill level. Your recruiter can share more about the specific salary range for the role location or, if the role can be performed remote, the specific salary range for your preferred location, during the hiring process.</p>\n       <p>Waymo employees are also eligible to participate in Waymo’s discretionary annual bonus program, equity incentive plan, and generous Company benefits program, subject to eligibility requirements.</p>\n      </div>\n      <div>\n       Salary Range\n      </div>\n      <div>\n       $192,000—$243,000 USD\n      </div>\n     </div>\n    </div>\n   </div>\n  </div>\n </div>\n</div>",
        "descriptionText": "MOUNTAIN VIEW, CALIFORNIA, UNITED STATES. NEW YORK CITY, NEW YORK, UNITED STATES FULL-TIME SOFTWARE ENGINEERING 3235\nWaymo is an autonomous driving technology company with the mission to be the most trusted driver. Since its start as the Google Self-Driving Car Project in 2009, Waymo has focused on building the Waymo Driver—The World's Most Experienced Driver™—to improve access to mobility while saving thousands of lives now lost to traffic crashes. The Waymo Driver powers Waymo One, a fully autonomous ride-hailing service, and can also be applied to a range of vehicle platforms and product use cases. The Waymo Driver has provided over one million rider-only trips, enabled by its experience autonomously driving tens of millions of miles on public roads and tens of billions in simulation across 13+ U.S. states.\n\nWaymo's Compute Team is tasked with a critical and exciting mission: We deliver the compute platform responsible for running the completely autonomous vehicle's software stack. To achieve our mission, we architect and create high-performance custom silicon; we develop system-level compute architectures that push the boundaries of performance, power, and latency; and we collaborate with many other teammates to ensure we design and improve hardware and software for maximum performance.\n\nIn this hybrid role, you will report to a Senior Staff Engineer.\n\nYou will:\n\nCollaborate with application teams to understand how to map newly developed and algorithms to GPU, allowing our cars to \"see\" further, operate smarter, and react faster\nBuild primitives and abstractions that allow for scaling our code-base to constantly evolving workloads and hardware\nImprove and add new compiler optimizations to promote producing optimized GPU assembly\nAnalyze performance counters, GPU micro-architectural features, and algorithms to identify optimization opportunities\nContribute to infrastructure that performs testing / static analysis to catch bugs early and create automated alerts to encourage following best GPU performance practices\nCo-design hardware features and evaluate trade-offs for future generations of our compute platform\n\nYou have:\n\n5+ years experience C++ programming skills\nAdvanced degree in Computer Science, similar technical field of study, or equivalent practical experience\n5+ years experience with GPU programming / optimization using CUDA or similar technologies\n1+ years experience with GPU architecture / programming model\n5+ years experience using performance analysis tools and debuggers\n5+ years experience with parallel computing/programming\n\nWe prefer:\n\nExperience with LLVM or SPIR-V open-source ecosystems or other compiler projects\nOperating systems or embedded software experience especially working on device drivers\nExperience with GPU optimization techniques: memory coalescing, register/shared memory tiling, pinned memory, and warp-level programming\nExperience with GPU libraries: CUB, CUTLASS, Thrust, or Eigen\nResearch experience in parallel algorithms, compilers, or computer architecture\nExperience with graphics workloads and shader programming\nML frameworks/compiler/library\n\n#LI-Hybrid\n\nThe expected base salary range for this full-time position across US locations is listed below. Actual starting pay will be based on job-related factors, including exact work location, experience, relevant training and education, and skill level. Your recruiter can share more about the specific salary range for the role location or, if the role can be performed remote, the specific salary range for your preferred location, during the hiring process.\n\nWaymo employees are also eligible to participate in Waymo’s discretionary annual bonus program, equity incentive plan, and generous Company benefits program, subject to eligibility requirements.\n\nSalary Range\n$192,000—$243,000 USD",
        "age": "1 day ago",
        "datePublished": "2024-12-30T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 243000,
          "salaryMin": 192000,
          "salarySource": "EXTRACTION",
          "salaryText": "$192,000 - $243,000 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "61dec2f588328f98",
        "source": "Waymo",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=61dec2f588328f98",
        "remoteLocation": false,
        "remoteWorkModel": {
          "inlineText": false,
          "text": "Hybrid work",
          "type": "REMOTE_HYBRID"
        },
        "scrapingInfo": {
          "page": 1,
          "index": 10
        }
      },
      {
        "title": "Quality Engineer - Health Software",
        "jobType": "Full-time",
        "companyName": "Apple",
        "companyUrl": "https://www.indeed.com/cmp/Apple",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/60c39b87a9a4eaa4df878c716840f84d",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/8c915d66415088a4c67d85ca195547dd",
        "rating": {
          "ariaContent": "4.1 out of 5 stars. Link to 13,469 company reviews (opens in a new tab)",
          "count": 13469,
          "countContent": "13,469 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Sunnyvale",
          "postalCode": null,
          "latitude": 37.36883,
          "longitude": -122.03635,
          "streetAddress": null,
          "formattedAddressLong": "Sunnyvale, CA",
          "formattedAddressShort": "Sunnyvale, CA"
        },
        "occupation": [
          "Technology Occupations",
          "Software Development & Architecture Occupations",
          "Software Quality Assurance Occupations"
        ],
        "benefits": [
          "Employee stock purchase plan",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "Retirement plan"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "Employee stock purchase plan",
          "Full-time",
          "NoSQL",
          "Mid-level",
          "Java",
          "Health insurance",
          "Microservices",
          "SQL",
          "Dental insurance",
          "RSU",
          "Scala",
          "Continuous integration",
          "SDKs",
          "RabbitMQ",
          "REST",
          "APIs",
          "Software testing",
          "Test cases",
          "Kafka",
          "4 years",
          "gRPC",
          "Retirement plan"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 133,
        "numOfCandidates": 5,
        "postedToday": true,
        "descriptionHtml": "<div>\n <b>Summary</b><br> <br> Posted: Oct 31, 2024<br> <br> Weekly Hours: <b>40</b><br> <br> Role Number:<b>200575727</b><br> <br> Join our Health Software team and play a critical role in ensuring the quality and reliability of our microservices architecture. You will be responsible for designing and driving test strategies to validate the performance, security, and scalability of microservices that power health-related applications. In this position, you'll collaborate with cross-functional teams to solve issues, automate testing processes, and help deliver seamless, high-quality services that prioritize data security and user experience in the health industry.<br> <br> <b>Description</b><br> <br> In this role, you will help: - Design and develop automation, tools, and applications including command-line interfaces, CI systems, and web applications. - Integrate apps and services together to help facilitate engineering, testing, and reporting for the Software and Quality Engineering teams. - Conduct performance and load testing to ensure backend services meet performance criteria - Work closely with developers, QA engineers, and other stakeholders to ensure quality throughout the development lifecycle - Document test strategies, test plans, and test results - Participate in code reviews to ensure test coverage and quality - Identify, document, and track bugs to closure - Drive release management process - Track delivery schedule and related dependencies. - Design and develop system test architecture.<br> <br> <b>Minimum Qualifications</b><br>\n <ul>\n  <li>4+ years of experience with test automaton development including creation and management of test frameworks from scratch.</li>\n  <li>Experience writing code in Scala/Java to test an API, SDK, or Framework.</li>\n  <li>Experience developing various forms of software tests in any of the following: unit, functional, performance, or stress</li>\n  <li>Experience in writing and automating test cases that interact with SQL and NoSQL databases.</li>\n  <li>Understanding of microservices design principles, service orchestration, and inter-service communication (e.g., REST, gRPC, messaging systems like Kafka or RabbitMQ).</li>\n </ul><br> <b> Preferred Qualifications</b><br>\n <ul>\n  <li>Excellent interpersonal skills and ability to work well with all levels of engineers and other teams</li>\n  <li>Familiarity with Wellness or Medical concepts</li>\n </ul><br> <b> Pay &amp; Benefits</b><br>\n <ul>\n  At Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $143,100 and $264,200, and your base pay will depend on your skills, qualifications, experience, and location.  Apple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.  Note: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n </ul><br> More<br>\n <ul>\n  <li>Apple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.</li>\n </ul>\n</div>",
        "descriptionText": "Summary\n\nPosted: Oct 31, 2024\n\nWeekly Hours: 40\n\nRole Number:200575727\n\nJoin our Health Software team and play a critical role in ensuring the quality and reliability of our microservices architecture. You will be responsible for designing and driving test strategies to validate the performance, security, and scalability of microservices that power health-related applications. In this position, you'll collaborate with cross-functional teams to solve issues, automate testing processes, and help deliver seamless, high-quality services that prioritize data security and user experience in the health industry.\n\nDescription\n\nIn this role, you will help: - Design and develop automation, tools, and applications including command-line interfaces, CI systems, and web applications. - Integrate apps and services together to help facilitate engineering, testing, and reporting for the Software and Quality Engineering teams. - Conduct performance and load testing to ensure backend services meet performance criteria - Work closely with developers, QA engineers, and other stakeholders to ensure quality throughout the development lifecycle - Document test strategies, test plans, and test results - Participate in code reviews to ensure test coverage and quality - Identify, document, and track bugs to closure - Drive release management process - Track delivery schedule and related dependencies. - Design and develop system test architecture.\n\nMinimum Qualifications\n\n4+ years of experience with test automaton development including creation and management of test frameworks from scratch.\nExperience writing code in Scala/Java to test an API, SDK, or Framework.\nExperience developing various forms of software tests in any of the following: unit, functional, performance, or stress\nExperience in writing and automating test cases that interact with SQL and NoSQL databases.\nUnderstanding of microservices design principles, service orchestration, and inter-service communication (e.g., REST, gRPC, messaging systems like Kafka or RabbitMQ).\n\nPreferred Qualifications\n\nExcellent interpersonal skills and ability to work well with all levels of engineers and other teams\nFamiliarity with Wellness or Medical concepts\n\nPay & Benefits\n\nAt Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $143,100 and $264,200, and your base pay will depend on your skills, qualifications, experience, and location.\n\nApple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.\n\nNote: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n\nMore\n\nApple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.",
        "age": "Just posted",
        "datePublished": "2025-01-01T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 264200,
          "salaryMin": 143100,
          "salarySource": "EXTRACTION",
          "salaryText": "$143,100 - $264,200 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "97cf0eda63f2a0ee",
        "source": "Apple",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=97cf0eda63f2a0ee",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 11
        }
      },
      {
        "title": "Order to Cash IT developer",
        "jobType": "Full-time",
        "companyName": "Procter & Gamble",
        "companyUrl": "https://www.indeed.com/cmp/Procter-&-Gamble",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/0edf936dd01c57d7adb6608c2ee78ff3",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/3d202e6ad16db490c3b298fe67035f7c",
        "rating": {
          "ariaContent": "4.1 out of 5 stars. Link to 8,161 company reviews (opens in a new tab)",
          "count": 8161,
          "countContent": "8,161 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "San Jose",
          "postalCode": null,
          "latitude": 37.33939,
          "longitude": -121.89496,
          "streetAddress": null,
          "formattedAddressLong": "San Jose, CA",
          "formattedAddressShort": "San Jose, CA"
        },
        "occupation": [
          "Data & Database Occupations",
          "Technology Occupations",
          "Database Administrators & Architects",
          "Database Architects"
        ],
        "benefits": [],
        "socialInsurance": [],
        "workingSystem": [],
        "attributes": [
          "Microsoft Powerpoint",
          "Microsoft Word",
          "Computer science",
          "Microsoft Excel",
          "Microsoft Outlook",
          "Computer Science",
          "SAP",
          "Full-time",
          "English",
          "Mid-level",
          "3 years",
          "Bachelor's degree",
          "Communication skills",
          "Information Technology"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 10,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <p><b>Job Location</b></p> San José\n <p></p>\n <p><b> Job Description</b></p>\n <p><b> Key Responsibilities:</b></p>\n <ul>\n  <li>Design, develop, and deploy Blue Prism automation solutions for SAP processes.</li>\n  <li>Collaborate with business analysts and stakeholders to gather requirements and ensure automation solutions align with business needs.</li>\n  <li>Perform testing and troubleshooting to ensure the quality and efficiency of automated processes.</li>\n  <li>Maintain and update existing Blue Prism processes and workflows.</li>\n  <li>Document and maintain technical specifications and project documentation.</li>\n  <li>Provide support and training to end-users and other team members as needed.</li>\n  <li>Stay up-to-date with the latest advancements in Blue Prism and SAP technologies.</li>\n </ul>\n <p></p>\n <p><b> Job Qualifications</b></p>\n <p><b> Qualifications:</b></p>\n <ul>\n  <li>Proven experience as a Blue Prism Developer, preferably with a focus on SAP integrations.</li>\n  <li>Proficiency in Microsoft O365 tools (Excel, Word, PowerPoint, Outlook, etc.).</li>\n  <li>Strong knowledge of SAP systems and processes.</li>\n  <li>B2 level of English proficiency, both written and spoken.</li>\n  <li>Excellent problem-solving skills and attention to detail.</li>\n  <li>Strong communication and interpersonal skills.</li>\n  <li>Ability to work independently and as part of a team.</li>\n  <li>Relevant certifications in Blue Prism.</li>\n </ul>\n <p><b>Education and Experience:</b></p>\n <ul>\n  <li>Bachelor’s degree in Computer Science, Information Technology, or a related field.</li>\n  <li>Minimum of 3 year of experience in RPA development with Blue Prism.</li>\n  <li>Experience in automating SAP processes and KNIME workflows.</li>\n </ul>\n <p></p>\n <p><b> Job Schedule</b></p> Full time\n <p></p>\n <p><b> Job Number</b></p> R000121442\n <p></p>\n <p><b> Job Segmentation</b></p> Experienced Professionals (Job Segmentation)\n</div>",
        "descriptionText": "Job Location\n\nSan José\n\nJob Description\n\nKey Responsibilities:\n\nDesign, develop, and deploy Blue Prism automation solutions for SAP processes.\nCollaborate with business analysts and stakeholders to gather requirements and ensure automation solutions align with business needs.\nPerform testing and troubleshooting to ensure the quality and efficiency of automated processes.\nMaintain and update existing Blue Prism processes and workflows.\nDocument and maintain technical specifications and project documentation.\nProvide support and training to end-users and other team members as needed.\nStay up-to-date with the latest advancements in Blue Prism and SAP technologies.\n\nJob Qualifications\n\nQualifications:\n\nProven experience as a Blue Prism Developer, preferably with a focus on SAP integrations.\nProficiency in Microsoft O365 tools (Excel, Word, PowerPoint, Outlook, etc.).\nStrong knowledge of SAP systems and processes.\nB2 level of English proficiency, both written and spoken.\nExcellent problem-solving skills and attention to detail.\nStrong communication and interpersonal skills.\nAbility to work independently and as part of a team.\nRelevant certifications in Blue Prism.\n\nEducation and Experience:\n\nBachelor’s degree in Computer Science, Information Technology, or a related field.\nMinimum of 3 year of experience in RPA development with Blue Prism.\nExperience in automating SAP processes and KNIME workflows.\n\nJob Schedule\n\nFull time\n\nJob Number\n\nR000121442\n\nJob Segmentation\n\nExperienced Professionals (Job Segmentation)",
        "age": "4 days ago",
        "datePublished": "2024-12-28T06:00:00.000Z",
        "expired": false,
        "jobKey": "7a29f695e0fe3b51",
        "source": "Procter & Gamble",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=7a29f695e0fe3b51",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 12
        }
      },
      {
        "title": "System Software Engineer, Vehicle Access",
        "jobType": "Full-time",
        "companyName": "Rivian and VW Group Technology",
        "companyUrl": "https://www.indeed.com/cmp/Rivian-and-Vw-Group-Technology",
        "companyLogoUrl": null,
        "campanyHeaderUrl": null,
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Palo Alto",
          "postalCode": "94304",
          "latitude": 37.419178,
          "longitude": -122.138214,
          "streetAddress": "607 Hansen Way",
          "formattedAddressLong": "Palo Alto, CA 94304",
          "formattedAddressShort": "Palo Alto, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [
          "Health insurance",
          "Dental insurance",
          "Vision insurance"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "MATLAB",
          "Hourly pay",
          "Email",
          "Full-time",
          "Information security",
          "Health insurance",
          "Dental insurance",
          "C++",
          "Electrical experience",
          "C",
          "Children",
          "RTOS",
          "Linux",
          "Vision insurance",
          "Senior level",
          "AI",
          "Robotics",
          "Communication skills",
          "Python",
          "Construction estimating"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 19,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n About Us: \n <div>\n  Rivian and Volkswagen Group Technologies is a joint venture between two industry leaders with a clear vision for automotive’s next chapter. From operating systems to zonal controllers to cloud and connectivity solutions, we’re addressing the challenges of electric vehicles through technology that will set the standards for software-defined vehicles around the world.\n </div>\n <div></div>\n <div>\n  <br> The road to the future is uncharted. By combining our expertise across connectivity, AI, security and more, we’ll map a new way forward. Working together, we’ll create a future that’s more connected, more intelligent, more sustainable for everyone.\n </div> Role Summary: \n <div>\n  In this role, you will be part of the vehicle access team, responsible for designing and building highly complex systems spanning multiple domains that bring new vehicle access features, improved functionality, and better performance to how users interact with our vehicles. In this multidisciplinary team, you will have the opportunity to work on all aspects of the software stack taking various vehicle access features from concept to production.\n </div> Responsibilities: \n <ul>\n  <li>Build scalable python based tools to enable rapid prototyping, debuggability, offline analysis and algorithm performance visualization.</li>\n  <li>Design, development, and implementation of sophisticated localization algorithms to accurately determine the user’s position and orientation to the vehicle in real-time.</li>\n  <li>Optimize algorithms for real-time performance on embedded systems, with a focus on computational efficiency and scalability.</li>\n  <li>Collaborate with test and integration engineers to integrate with other system components, ensuring seamless vehicle operation.</li>\n  <li>Leverage AI and machine learning tools to contribute to the team's data based insights generation efforts.</li>\n  <li>Take ideas through stages of concept, design, execution, deployment, and hardening in a production environment.</li>\n  <li>Work closely with other development and cross-functional team members in software such as mobile app, body controls, product security, infotainment, VUX teams, and EE/Hardware teams not only in vehicle access but other cross functional initiatives.</li>\n </ul> Qualifications: \n <ul>\n  <li>The ideal candidate will have a strong background in Electrical and Computer Engineering, Robotics, Computer Science, or related fields, with a large focus on control systems, sensor fusion, state estimation, or related areas.</li>\n  <li>Proficiency in C/C++ and Python.</li>\n  <li>Understanding of Real Time Operating Systems (RTOS) and Linux fundamentals</li>\n  <li>Curious, enjoys rapid prototyping and working collaboratively in a fast-paced R&amp;D environment, with excellent problem-solving and communication skills.</li>\n  <li>Experience with Matlab or related simulation tools is a nice to have</li>\n </ul>\n <div></div>\n <div>\n  <b><br> Ideal Qualifications:</b>\n </div>\n <ul>\n  <li>Experience with wireless networks including BLE, UWB, 802.15.4, and NFC</li>\n </ul> Pay Disclosure: \n <div>\n  <b> Salary Range/Hourly Rate for California Based Applicants:</b> $146,900 - $183,600 USD (actual compensation will be determined based on experience, location, and other factors permitted by law).\n </div>\n <div></div>\n <div>\n  <b><br> Benefits Summary:</b> Rivian and Volkswagen Group Technologies provides robust medical/Rx, dental and vision insurance packages for full-time employees, their spouse or domestic partner, and children up to age 26. Coverage is effective on the first day of employment.\n </div> Company Statements: \n <h4 class=\"jobSectionHeader\"><b>Equal Opportunity</b></h4>\n <div>\n  Rivian and Volkswagen Group Technologies is committed to creating a diverse environment and is proud to be an equal opportunity employer. All qualified applicants will receive consideration for employment without regard to race, color, religion, national origin, ancestry, sex, sexual orientation, gender, gender expression, gender identity, genetic information or characteristics, physical or mental disability, marital/domestic partner status, age, military/veteran status, medical condition, or any other characteristic protected by law. We are also committed to ensuring compliance with all applicable fair employment practice laws regarding citizenship and immigration status.\n </div>\n <div></div>\n <div>\n  <br> Rivian and Volkswagen Group Technologies is committed to ensuring that our hiring process is accessible for persons with disabilities. If you have a disability or limitation, such as those covered by the Americans with Disabilities Act, that requires accommodations to assist you in the search and application process, please email us at candidateaccommodations@rivian.com.\n </div>\n <h4 class=\"jobSectionHeader\"><b> Candidate Data Privacy</b></h4>\n <div>\n  Rivian and VW Group Technologies (“Rivian and Volkswagen Group Technologies”) may collect, use and disclose your personal information or personal data (within the meaning of the applicable data protection laws) when you apply for employment and/or participate in our recruitment processes (“Candidate Personal Data”). This data includes contact, demographic, communications, educational, professional, employment, social media/website, network/device, recruiting system usage/interaction, security and preference information. Rivian and Volkswagen Group Technologies may use your Candidate Personal Data for the purposes of (i) tracking interactions with our recruiting system; (ii) carrying out, analyzing and improving our application and recruitment process, including assessing you and your application and conducting employment, background and reference checks; (iii) establishing an employment relationship or entering into an employment contract with you; (iv) complying with our legal, regulatory and corporate governance obligations; (v) recordkeeping; (vi) ensuring network and information security and preventing fraud; and (vii) as otherwise required or permitted by applicable law.\n </div>\n <div></div>\n <div>\n  <br> Rivian and Volkswagen Group Technologies may share your Candidate Personal Data with (i) internal personnel who have a need to know such information in order to perform their duties, including individuals on our People Team, Finance, Legal, and the team(s) with the position(s) for which you are applying; (ii) Rivian and Volkswagen Group Technologies affiliates; and (iii) Rivian and Volkswagen Group Technologies’ service providers, including providers of background checks, staffing services, and cloud services.\n </div>\n <div></div>\n <div>\n  <br> Rivian and Volkswagen Group Technologies may transfer or store internationally your Candidate Personal Data, including to or in the United States, Canada, and the European Union and in the cloud, and this data may be subject to the laws and accessible to the courts, law enforcement and national security authorities of such jurisdictions.\n </div>\n <div></div>\n <div>\n  <b><br> Please note that we are currently not accepting applications from third party application services.</b>\n </div>\n</div>",
        "descriptionText": "About Us:\n\nRivian and Volkswagen Group Technologies is a joint venture between two industry leaders with a clear vision for automotive’s next chapter. From operating systems to zonal controllers to cloud and connectivity solutions, we’re addressing the challenges of electric vehicles through technology that will set the standards for software-defined vehicles around the world.\n\nThe road to the future is uncharted. By combining our expertise across connectivity, AI, security and more, we’ll map a new way forward. Working together, we’ll create a future that’s more connected, more intelligent, more sustainable for everyone.\n\nRole Summary:\n\nIn this role, you will be part of the vehicle access team, responsible for designing and building highly complex systems spanning multiple domains that bring new vehicle access features, improved functionality, and better performance to how users interact with our vehicles. In this multidisciplinary team, you will have the opportunity to work on all aspects of the software stack taking various vehicle access features from concept to production.\n\nResponsibilities:\nBuild scalable python based tools to enable rapid prototyping, debuggability, offline analysis and algorithm performance visualization.\nDesign, development, and implementation of sophisticated localization algorithms to accurately determine the user’s position and orientation to the vehicle in real-time.\nOptimize algorithms for real-time performance on embedded systems, with a focus on computational efficiency and scalability.\nCollaborate with test and integration engineers to integrate with other system components, ensuring seamless vehicle operation.\nLeverage AI and machine learning tools to contribute to the team's data based insights generation efforts.\nTake ideas through stages of concept, design, execution, deployment, and hardening in a production environment.\nWork closely with other development and cross-functional team members in software such as mobile app, body controls, product security, infotainment, VUX teams, and EE/Hardware teams not only in vehicle access but other cross functional initiatives.\nQualifications:\nThe ideal candidate will have a strong background in Electrical and Computer Engineering, Robotics, Computer Science, or related fields, with a large focus on control systems, sensor fusion, state estimation, or related areas.\nProficiency in C/C++ and Python.\nUnderstanding of Real Time Operating Systems (RTOS) and Linux fundamentals\nCurious, enjoys rapid prototyping and working collaboratively in a fast-paced R&D environment, with excellent problem-solving and communication skills.\nExperience with Matlab or related simulation tools is a nice to have\n\nIdeal Qualifications:\n\nExperience with wireless networks including BLE, UWB, 802.15.4, and NFC\nPay Disclosure:\n\nSalary Range/Hourly Rate for California Based Applicants: $146,900 - $183,600 USD (actual compensation will be determined based on experience, location, and other factors permitted by law).\n\nBenefits Summary: Rivian and Volkswagen Group Technologies provides robust medical/Rx, dental and vision insurance packages for full-time employees, their spouse or domestic partner, and children up to age 26. Coverage is effective on the first day of employment.\n\nCompany Statements:\nEqual Opportunity\n\nRivian and Volkswagen Group Technologies is committed to creating a diverse environment and is proud to be an equal opportunity employer. All qualified applicants will receive consideration for employment without regard to race, color, religion, national origin, ancestry, sex, sexual orientation, gender, gender expression, gender identity, genetic information or characteristics, physical or mental disability, marital/domestic partner status, age, military/veteran status, medical condition, or any other characteristic protected by law. We are also committed to ensuring compliance with all applicable fair employment practice laws regarding citizenship and immigration status.\n\nRivian and Volkswagen Group Technologies is committed to ensuring that our hiring process is accessible for persons with disabilities. If you have a disability or limitation, such as those covered by the Americans with Disabilities Act, that requires accommodations to assist you in the search and application process, please email us at candidateaccommodations@rivian.com.\n\nCandidate Data Privacy\n\nRivian and VW Group Technologies (“Rivian and Volkswagen Group Technologies”) may collect, use and disclose your personal information or personal data (within the meaning of the applicable data protection laws) when you apply for employment and/or participate in our recruitment processes (“Candidate Personal Data”). This data includes contact, demographic, communications, educational, professional, employment, social media/website, network/device, recruiting system usage/interaction, security and preference information. Rivian and Volkswagen Group Technologies may use your Candidate Personal Data for the purposes of (i) tracking interactions with our recruiting system; (ii) carrying out, analyzing and improving our application and recruitment process, including assessing you and your application and conducting employment, background and reference checks; (iii) establishing an employment relationship or entering into an employment contract with you; (iv) complying with our legal, regulatory and corporate governance obligations; (v) recordkeeping; (vi) ensuring network and information security and preventing fraud; and (vii) as otherwise required or permitted by applicable law.\n\nRivian and Volkswagen Group Technologies may share your Candidate Personal Data with (i) internal personnel who have a need to know such information in order to perform their duties, including individuals on our People Team, Finance, Legal, and the team(s) with the position(s) for which you are applying; (ii) Rivian and Volkswagen Group Technologies affiliates; and (iii) Rivian and Volkswagen Group Technologies’ service providers, including providers of background checks, staffing services, and cloud services.\n\nRivian and Volkswagen Group Technologies may transfer or store internationally your Candidate Personal Data, including to or in the United States, Canada, and the European Union and in the cloud, and this data may be subject to the laws and accessible to the courts, law enforcement and national security authorities of such jurisdictions.\n\nPlease note that we are currently not accepting applications from third party application services.",
        "age": "1 day ago",
        "datePublished": "2024-12-30T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 183600,
          "salaryMin": 146900,
          "salarySource": "EXTRACTION",
          "salaryText": "$146,900 - $183,600 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "92135eda9d7f5a60",
        "source": "Rivian and VW Group Technology",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=92135eda9d7f5a60",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 13
        }
      },
      {
        "title": "Imaging and Software Quality Assurance Engineer, Photos",
        "jobType": "Full-time",
        "companyName": "Apple",
        "companyUrl": "https://www.indeed.com/cmp/Apple",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/60c39b87a9a4eaa4df878c716840f84d",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/8c915d66415088a4c67d85ca195547dd",
        "rating": {
          "ariaContent": "4.1 out of 5 stars. Link to 13,469 company reviews (opens in a new tab)",
          "count": 13469,
          "countContent": "13,469 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Cupertino",
          "postalCode": null,
          "latitude": 37.323,
          "longitude": -122.03218,
          "streetAddress": null,
          "formattedAddressLong": "Cupertino, CA",
          "formattedAddressShort": "Cupertino, CA"
        },
        "occupation": [
          "Technology Occupations",
          "Software Development & Architecture Occupations",
          "Software Quality Assurance Occupations"
        ],
        "benefits": [
          "Employee stock purchase plan",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "Retirement plan"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "Computer science",
          "Management",
          "Computer Science",
          "Employee stock purchase plan",
          "iOS",
          "Test automation",
          "Full-time",
          "Mid-level",
          "Health insurance",
          "Dental insurance",
          "Analysis skills",
          "RSU",
          "Bachelor's degree",
          "Continuous integration",
          "Computer Engineering",
          "Organizational skills",
          "Mac OS",
          "4 years",
          "Communication skills",
          "Python",
          "Editing",
          "Retirement plan"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 25,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <b>Summary</b><br> <br> Posted: Sep 24, 2024<br> <br> Weekly Hours: <b>40</b><br> <br> Role Number:<b>200555603</b><br> <br> At Apple you can be your best creative and professional self. In the Camera &amp; Photos group, combining incredible hardware and fantastic software to make magic for millions is our purpose and passion - from capturing those special personal moments to preserving, enriching and sharing those memories to family and friends. To power this world-class experience it takes a dedicated team to ensure that quality never falls short of the Apple Promise. You can be one of those champions! The Photos Quality Engineering team is offering a unique opportunity to join us in driving the quality growth for foundational imaging technologies and the features built upon on them as part of Apple's great photographic software. Take your career in quality engineering to the next level as part of an experienced and passionate cohort driving the full range of qualifications - from hands-on user experiences to lower-level data validations, on device and in the cloud.<br> <br> <b>Description</b><br> <br> This individual contributor will engage with peers in development and quality to ensure imaging technology frameworks and the user-level features built on top of them are always functioning at the highest standard. Your responsibilities will focus on functional, regression and integration testing across our platforms, eg, macOS, tvOS, iOS and iPadOS. As part of a supportive team you will independently investigate, triage and escalate the problems you and others discover. Daily work focuses on iterative software validation, of existing and new features &amp; technologies, using both manual and automated approaches. The demanding work environment requires balancing differing phases of multiple concurrent projects while delivering your important contributions to their success. Accountable for driving and triaging automation as needed including some script authoring. Excellent oral and written communication and organizational skills are needed due to the detailed and critical nature of the work as well as the extensive collaboration with others.<br> <br> <b>Minimum Qualifications</b><br>\n <ul>\n  <li>4+ years of professional experience in the lifecycles of consumer software test engineering, using both manual and automated methods, underpinned by a passion for delivering great products at high quality</li>\n  <li>Strong analytical and problem-solving skills; experience in writing and running lengthy test plans; discovering and documenting software and hardware defects; prioritizing and escalating problems to peers and management, driving their resolution</li>\n  <li>Excellent communication skills, both written and verbal; comfortable with distilling complex technical matters to concise and actionable tasks; working cross-functionally to everyone's benefit</li>\n  <li>Confident and familiar with Apple’s current hardware and software ecosystem</li>\n  <li>Professional experience qualifying imaging correctness at the functional and framework level for user-facing features</li>\n </ul><br> <b> Preferred Qualifications</b><br>\n <ul>\n  <li>Leading a team of peers in testing and delivering spec-driven interdependent features with a strong sense of ownership in the outcome while also uplifting those around you</li>\n  <li>Testing with digital media acquisition, augmentation &amp; editing, with an eye for evaluating photographic correctness and attractiveness; strong familiarity with Camera, Photos, and other video &amp; photographic offerings</li>\n  <li>Pragmatic proficiency in common shell/CLI methods as well as some test automation experience, ideally with Python and XCTest; remote device testing and general CI processes are valuable</li>\n  <li>Very comfortable sharing considered opinions, taking the time to get details right yet staying true to the bigger picture</li>\n  <li>Proficient at balancing multiple efforts simultaneously and meeting strict deadlines</li>\n  <li>Bachelors degree in Computer Science, Computer Engineering or equivalent experience</li>\n </ul><br> <b> Pay &amp; Benefits</b><br>\n <ul>\n  At Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $112,900 and $234,700, and your base pay will depend on your skills, qualifications, experience, and location.  Apple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.  Note: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n </ul><br> More<br>\n <ul>\n  <li>Apple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.</li>\n </ul>\n</div>",
        "descriptionText": "Summary\n\nPosted: Sep 24, 2024\n\nWeekly Hours: 40\n\nRole Number:200555603\n\nAt Apple you can be your best creative and professional self. In the Camera & Photos group, combining incredible hardware and fantastic software to make magic for millions is our purpose and passion - from capturing those special personal moments to preserving, enriching and sharing those memories to family and friends. To power this world-class experience it takes a dedicated team to ensure that quality never falls short of the Apple Promise. You can be one of those champions! The Photos Quality Engineering team is offering a unique opportunity to join us in driving the quality growth for foundational imaging technologies and the features built upon on them as part of Apple's great photographic software. Take your career in quality engineering to the next level as part of an experienced and passionate cohort driving the full range of qualifications - from hands-on user experiences to lower-level data validations, on device and in the cloud.\n\nDescription\n\nThis individual contributor will engage with peers in development and quality to ensure imaging technology frameworks and the user-level features built on top of them are always functioning at the highest standard. Your responsibilities will focus on functional, regression and integration testing across our platforms, eg, macOS, tvOS, iOS and iPadOS. As part of a supportive team you will independently investigate, triage and escalate the problems you and others discover. Daily work focuses on iterative software validation, of existing and new features & technologies, using both manual and automated approaches. The demanding work environment requires balancing differing phases of multiple concurrent projects while delivering your important contributions to their success. Accountable for driving and triaging automation as needed including some script authoring. Excellent oral and written communication and organizational skills are needed due to the detailed and critical nature of the work as well as the extensive collaboration with others.\n\nMinimum Qualifications\n\n4+ years of professional experience in the lifecycles of consumer software test engineering, using both manual and automated methods, underpinned by a passion for delivering great products at high quality\nStrong analytical and problem-solving skills; experience in writing and running lengthy test plans; discovering and documenting software and hardware defects; prioritizing and escalating problems to peers and management, driving their resolution\nExcellent communication skills, both written and verbal; comfortable with distilling complex technical matters to concise and actionable tasks; working cross-functionally to everyone's benefit\nConfident and familiar with Apple’s current hardware and software ecosystem\nProfessional experience qualifying imaging correctness at the functional and framework level for user-facing features\n\nPreferred Qualifications\n\nLeading a team of peers in testing and delivering spec-driven interdependent features with a strong sense of ownership in the outcome while also uplifting those around you\nTesting with digital media acquisition, augmentation & editing, with an eye for evaluating photographic correctness and attractiveness; strong familiarity with Camera, Photos, and other video & photographic offerings\nPragmatic proficiency in common shell/CLI methods as well as some test automation experience, ideally with Python and XCTest; remote device testing and general CI processes are valuable\nVery comfortable sharing considered opinions, taking the time to get details right yet staying true to the bigger picture\nProficient at balancing multiple efforts simultaneously and meeting strict deadlines\nBachelors degree in Computer Science, Computer Engineering or equivalent experience\n\nPay & Benefits\n\nAt Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $112,900 and $234,700, and your base pay will depend on your skills, qualifications, experience, and location.\n\nApple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.\n\nNote: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n\nMore\n\nApple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.",
        "age": "6 days ago",
        "datePublished": "2024-12-26T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 234700,
          "salaryMin": 112900,
          "salarySource": "EXTRACTION",
          "salaryText": "$112,900 - $234,700 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "4bee2d5a2ffc8bc1",
        "source": "Apple",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=4bee2d5a2ffc8bc1",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 14
        }
      },
      {
        "title": "Software Engineering Manager, Mail Intelligence",
        "jobType": "Full-time",
        "companyName": "Apple",
        "companyUrl": "https://www.indeed.com/cmp/Apple",
        "companyLogoUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/60c39b87a9a4eaa4df878c716840f84d",
        "campanyHeaderUrl": "https://d2q79iu7y748jz.cloudfront.net/s/_headerimage/1960x400/8c915d66415088a4c67d85ca195547dd",
        "rating": {
          "ariaContent": "4.1 out of 5 stars. Link to 13,469 company reviews (opens in a new tab)",
          "count": 13469,
          "countContent": "13,469 reviews",
          "descriptionContent": "Read what people are saying about working here.",
          "rating": 4.1,
          "showCount": true,
          "showDescription": true,
          "size": null
        },
        "employerLastReviewed": null,
        "employerInsightsModel": {
          "isActivelyReviewApplications": false,
          "lastActiveTimeInDays": -1,
          "mobVjEmpSectionTstGrp": -1,
          "percentageResponsiveness": -1,
          "responseTimeInDays": -1,
          "responseTimeInHours": -1
        },
        "location": {
          "countryCode": "US",
          "city": "Cupertino",
          "postalCode": null,
          "latitude": 37.323,
          "longitude": -122.03218,
          "streetAddress": null,
          "formattedAddressLong": "Cupertino, CA",
          "formattedAddressShort": "Cupertino, CA"
        },
        "occupation": [
          "Software Development Occupations",
          "Technology Occupations",
          "Software Development & Architecture Occupations"
        ],
        "benefits": [
          "Employee stock purchase plan",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "Retirement plan"
        ],
        "socialInsurance": [
          "Health insurance"
        ],
        "workingSystem": [],
        "attributes": [
          "Employee stock purchase plan",
          "iOS",
          "Full-time",
          "Health insurance",
          "Dental insurance",
          "RSU",
          "Machine learning",
          "Mac OS",
          "Senior level",
          "AI",
          "Retirement plan"
        ],
        "hiringDemand": {
          "isUrgentHire": false,
          "isHighVolumeHiring": false
        },
        "organicApplyStarts": 17,
        "numOfCandidates": 5,
        "postedToday": false,
        "descriptionHtml": "<div>\n <b>Summary</b><br> <br> Posted: Aug 28, 2024<br> <br> Weekly Hours: <b>40</b><br> <br> Role Number:<b>200563420</b><br> <br> Imagine the possibilities when intelligence meets innovation in one of the most widely used applications at Apple. As the Mail Intelligence Engineering Manager, you will be at the forefront of integrating cutting-edge machine learning technologies into the Mail application across iOS, iPadOS, macOS, and visionOS. Your role is pivotal in creating intelligent features that transform the user experience, from enhancing Mail Search to introducing generative, summarization, and categorization features. If you have a passion for backend client work, such as indexing information and enabling data-driven models, coupled with strong product sense and a desire to lead in a groundbreaking area, this is the role for you!<br> <br> <b>Description</b><br> <br> As the Mail Intelligence Engineering Manager, you will lead a team of engineers dedicated to bringing intelligence to Apple Mail across our platforms. Your leadership will guide the development of features that leverage machine learning to create a smarter, more intuitive Mail experience. You will collaborate with teams across Apple to integrate Apple Intelligence, enhance Mail Search, and pioneer new capabilities in the app. This role requires both hands-on technical management and strategic vision to push the boundaries of what the Mail app can do: - Lead and mentor the Mail Intelligence engineering team, fostering a culture of innovation and inclusivity. - Collaborate with cross-functional teams, including machine learning, project management, and design, to define and implement intelligent features. - Oversee the integration of new technologies into the Mail app, driving improvements in areas like search, generative features, summarization, and categorization.. - Ensure high performance, reliability, and scalability of the backend systems that power these intelligent features. - Represent the Mail Intelligence team in technical and project meetings, driving alignment with broader Apple initiatives.<br> <br> <b>Minimum Qualifications</b><br>\n <ul>\n  <li>You care about helping others grow in their careers at Apple.</li>\n  <li>You have a history of hiring and mentoring a diverse team of engineers.</li>\n  <li>You prioritize building an inclusive team culture where everyone can be heard and the best ideas are the ones we pursue.</li>\n  <li>You have strong software engineering skills and can act as an arbitrator for tough technical debates.</li>\n  <li>You aspire to take an Apple-wide perspective in making decisions.</li>\n </ul><br> <b> Preferred Qualifications</b><br>\n <ul>\n  <li>You have expertise in machine learning and AI integration, particularly in building intelligent features within consumer applications.</li>\n </ul><br> <b> Pay &amp; Benefits</b><br>\n <ul>\n  At Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $190,700 and $329,600, and your base pay will depend on your skills, qualifications, experience, and location.  Apple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.  Note: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n </ul><br> More<br>\n <ul>\n  <li>Apple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.</li>\n </ul>\n</div>",
        "descriptionText": "Summary\n\nPosted: Aug 28, 2024\n\nWeekly Hours: 40\n\nRole Number:200563420\n\nImagine the possibilities when intelligence meets innovation in one of the most widely used applications at Apple. As the Mail Intelligence Engineering Manager, you will be at the forefront of integrating cutting-edge machine learning technologies into the Mail application across iOS, iPadOS, macOS, and visionOS. Your role is pivotal in creating intelligent features that transform the user experience, from enhancing Mail Search to introducing generative, summarization, and categorization features. If you have a passion for backend client work, such as indexing information and enabling data-driven models, coupled with strong product sense and a desire to lead in a groundbreaking area, this is the role for you!\n\nDescription\n\nAs the Mail Intelligence Engineering Manager, you will lead a team of engineers dedicated to bringing intelligence to Apple Mail across our platforms. Your leadership will guide the development of features that leverage machine learning to create a smarter, more intuitive Mail experience. You will collaborate with teams across Apple to integrate Apple Intelligence, enhance Mail Search, and pioneer new capabilities in the app. This role requires both hands-on technical management and strategic vision to push the boundaries of what the Mail app can do: - Lead and mentor the Mail Intelligence engineering team, fostering a culture of innovation and inclusivity. - Collaborate with cross-functional teams, including machine learning, project management, and design, to define and implement intelligent features. - Oversee the integration of new technologies into the Mail app, driving improvements in areas like search, generative features, summarization, and categorization.. - Ensure high performance, reliability, and scalability of the backend systems that power these intelligent features. - Represent the Mail Intelligence team in technical and project meetings, driving alignment with broader Apple initiatives.\n\nMinimum Qualifications\n\nYou care about helping others grow in their careers at Apple.\nYou have a history of hiring and mentoring a diverse team of engineers.\nYou prioritize building an inclusive team culture where everyone can be heard and the best ideas are the ones we pursue.\nYou have strong software engineering skills and can act as an arbitrator for tough technical debates.\nYou aspire to take an Apple-wide perspective in making decisions.\n\nPreferred Qualifications\n\nYou have expertise in machine learning and AI integration, particularly in building intelligent features within consumer applications.\n\nPay & Benefits\n\nAt Apple, base pay is one part of our total compensation package and is determined within a range. This provides the opportunity to progress as you grow and develop within a role. The base pay range for this role is between $190,700 and $329,600, and your base pay will depend on your skills, qualifications, experience, and location.\n\nApple employees also have the opportunity to become an Apple shareholder through participation in Apple’s discretionary employee stock programs. Apple employees are eligible for discretionary restricted stock unit awards, and can purchase Apple stock at a discount if voluntarily participating in Apple’s Employee Stock Purchase Plan. You’ll also receive benefits including: Comprehensive medical and dental coverage, retirement benefits, a range of discounted products and free services, and for formal education related to advancing your career at Apple, reimbursement for certain educational expenses - including tuition. Additionally, this role might be eligible for discretionary bonuses or commission payments as well as relocation. Learn more about Apple Benefits.\n\nNote: Apple benefit, compensation and employee stock programs are subject to eligibility requirements and other terms of the applicable plan or program.\n\nMore\n\nApple is an equal opportunity employer that is committed to inclusion and diversity. We take affirmative action to ensure equal opportunity for all applicants without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, Veteran status, or other legally protected characteristics. Learn more about your EEO rights as an applicant.",
        "age": "2 days ago",
        "datePublished": "2024-12-30T06:00:00.000Z",
        "expired": false,
        "salary": {
          "featureTokens": [],
          "matchingSalary": false,
          "minimumPayPreferencePresent": false,
          "salaryCurrency": "USD",
          "salaryLabel": {
            "scope": null,
            "usefulPercent": null
          },
          "salaryMax": 329600,
          "salaryMin": 190700,
          "salarySource": "EXTRACTION",
          "salaryText": "$190,700 - $329,600 a year",
          "salaryTextFormatted": false,
          "salaryType": "YEARLY"
        },
        "jobKey": "38ff802ed8ba9ba9",
        "source": "Apple",
        "locale": "en_US",
        "jobUrl": "https://www.indeed.com/viewjob?jk=38ff802ed8ba9ba9",
        "remoteLocation": false,
        "remoteWorkModel": null,
        "scrapingInfo": {
          "page": 1,
          "index": 15
        }
      }
    ]
  },
  "delay": 0,
  "priority": 0,
  "attemptsStarted": 1,
  "attemptsMade": 1,
  "timestamp": 1735758398960,
  "finishedOn": 1735758429810,
  "processedOn": 1735758398963
}
```


```
import requests

url = "https://google-jobs-api.p.rapidapi.com/google-jobs/relocation"

querystring = {"include":"senior engineer"}

headers = {
	"x-rapidapi-key": "3a7xxx",
	"x-rapidapi-host": "google-jobs-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())
```

```

```