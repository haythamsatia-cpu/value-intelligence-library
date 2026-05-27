from django.core.management.base import BaseCommand

from taxonomy.models import Domain, Subdomain
from taxonomy.utils import UNCATEGORIZED_DOMAIN_NAME, get_or_create_uncategorized_domain

DEFAULT_TAXONOMY = {
    'Contracts Management': [
        'Contract Formation & Award',
        'Contract Administration',
        'Variations & Change Management',
        'NEC Contracts',
        'FIDIC Contracts',
        'JCT & Traditional Forms',
        'Subcontract Management',
        'Contract Close-Out',
    ],
    'Project Controls': [
        'Performance Measurement',
        'Reporting & Dashboards',
        'Governance & Assurance',
        'Integrated Cost-Schedule Control',
        'Earned Value Management',
        'KPIs & Metrics',
        'Change Control',
        'Baseline Management',
    ],
    'Claims Management': [
        'Claim Strategy & Notice',
        'Delay Analysis',
        'Quantum & Damages',
        'Dispute Avoidance',
        'Extension of Time',
        'Prolongation Costs',
        'Claims Documentation',
        'Negotiation & Settlement',
    ],
    'Construction Operations Management': [
        'Site Logistics',
        'Labor & Crew Management',
        'Plant & Equipment',
        'Temporary Works',
        'Site Establishment',
        'Production Planning',
        'Handover & Commissioning',
        'Operational Safety Interface',
    ],
    'Cost Management': [
        'Estimating',
        'Budgeting',
        'Cost Control',
        'Cash Flow Forecasting',
        'Final Account',
        'Value Engineering',
        'Lifecycle Costing',
        'Cost Risk Allowances',
    ],
    'Planning & Scheduling': [
        'Critical Path Method',
        'Resource Loading',
        'Look-Ahead Planning',
        '4D / BIM Planning',
        'Schedule Risk Analysis',
        'Progress Measurement',
        'Recovery Schedules',
        'Milestone Planning',
    ],
    'Procurement Management': [
        'Procurement Strategy',
        'Tendering & Bidding',
        'Supplier Selection',
        'Materials Management',
        'Long-Lead Items',
        'Contract Packages',
        'Supply Chain Risk',
        'Procurement Compliance',
    ],
    'Commercial Management': [
        'Commercial Strategy',
        'Payment & Certification',
        'Risk & Opportunity Register',
        'Margins & Mark-Up',
        'Commercial Reporting',
        'Bonds & Guarantees',
        'Insurance & Indemnities',
        'Client Relations',
    ],
    'Risk Management': [
        'Risk Identification',
        'Qualitative Risk Assessment',
        'Quantitative Risk Analysis',
        'Mitigation Planning',
        'Contingency Management',
        'HSE Risk',
        'Enterprise Risk',
        'Lessons Learned Integration',
    ],
    'Document Control': [
        'Document Numbering',
        'Transmittals & Submittals',
        'As-Built Records',
        'BIM Information Management',
        'Correspondence Management',
        'Records Retention',
        'Version Control',
        'Audit Trails',
    ],
    'Construction Finance': [
        'Project Accounting',
        'Funding & Cash Management',
        'Tax & Compliance',
        'Financial Reporting',
        'Working Capital',
        'JV & Consortium Accounting',
        'Currency & Inflation',
        'Audit & Assurance',
    ],
    'Leadership & Management': [
        'Team Leadership',
        'Stakeholder Management',
        'Communication',
        'Decision Making',
        'Ethics & Professional Conduct',
        'Coaching & Mentoring',
        'Conflict Resolution',
        'Organizational Design',
    ],
}


class Command(BaseCommand):
    help = 'Seed default construction management domains and starter subdomains.'

    def handle(self, *args, **options):
        domains_created = 0
        subdomains_created = 0

        uncategorized, created = Domain.objects.get_or_create(
            name=UNCATEGORIZED_DOMAIN_NAME,
            defaults={
                'description': 'Fallback domain for fast-imported units pending taxonomy review.',
            },
        )
        if created:
            domains_created += 1
            self.stdout.write(self.style.SUCCESS(f'Created domain: {UNCATEGORIZED_DOMAIN_NAME}'))
        else:
            get_or_create_uncategorized_domain()

        for domain_name, subdomain_names in DEFAULT_TAXONOMY.items():
            domain, created = Domain.objects.get_or_create(
                name=domain_name,
                defaults={'description': f'Starter domain: {domain_name}'},
            )
            if created:
                domains_created += 1
                self.stdout.write(self.style.SUCCESS(f'Created domain: {domain_name}'))
            else:
                self.stdout.write(f'Domain exists: {domain_name}')

            for sub_name in subdomain_names:
                _, sub_created = Subdomain.objects.get_or_create(
                    domain=domain,
                    name=sub_name,
                    defaults={'description': ''},
                )
                if sub_created:
                    subdomains_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. {domains_created} domain(s) and {subdomains_created} subdomain(s) created.'
            )
        )
