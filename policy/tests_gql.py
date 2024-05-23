import base64
import json
from dataclasses import dataclass
from core.models import User
from core.test_helpers import create_test_interactive_user
from django.conf import settings
from graphene_django.utils.testing import GraphQLTestCase
from graphql_jwt.shortcuts import get_token
#credits https://docs.graphene-python.org/projects/django/en/latest/testing/


@dataclass
class DummyContext:
    """ Just because we need a context to generate. """
    user: User

class PolicyGraphQLTestCase(GraphQLTestCase):
    GRAPHQL_URL = f'/{settings.SITE_ROOT()}graphql'
    # This is required by some version of graphene but is never used. It should be set to the schema but the import
    # is shown as an error in the IDE, so leaving it as True.
    GRAPHQL_SCHEMA = True
    admin_user = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = create_test_interactive_user(username="testLocationAdmin")
        cls.admin_token = get_token(cls.admin_user, DummyContext(user=cls.admin_user))
    
    def test_insuree_policy_query(self):
        
        response = self.query(
            '''
            query {
                policies(first: 10,orderBy: ["-enrollDate"], balanceLte: 100)
                {
                    totalCount
                    pageInfo { hasNextPage, hasPreviousPage, startCursor, endCursor}
                    edges
                    {
                        node
                        {
                            uuid,product{id,code,name,location{id}},officer{id,uuid,code,lastName,otherNames},family{id,uuid,headInsuree{id chfId uuid lastName otherNames},location{id,uuid,code,name,type,parent{id,uuid,code,name,type,parent{id,uuid,code,name,type,parent{id,uuid,code,name,type}}}}},enrollDate,effectiveDate,startDate,expiryDate,stage,status,value,sumPremiums,validityFrom,validityTo
                        }
                    }
                }
            }
            ''',
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"},
        )

        content = json.loads(response.content)

        # This validates the status code and if you get errors
        self.assertResponseNoErrors(response)

        # Add some more asserts if you like
        ...

    def test_query_with_variables(self):
        response = self.query(
            '''
    
            query policiesByInsuree($chfid: String!, $targetDate:  Date! ) {
                policiesByInsuree(chfId:$chfid ,targetDate: $targetDate)
                {
                    totalCount
                    pageInfo { hasNextPage, hasPreviousPage, startCursor, endCursor}
                    edges
                    {
                        node
                        {
                            policyUuid,productCode,productName,officerCode,officerName,enrollDate,effectiveDate,startDate,expiryDate,status,policyValue,balance,ded,dedInPatient,dedOutPatient,ceiling,ceilingInPatient,ceilingOutPatient
                        }
                    }
                }
            }
            ''',
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"},
            variables={'chfid': "070707070", 'targetDate':"2019-01-01"}
        )

        content = json.loads(response.content)

        # This validates the status code and if you get errors
        self.assertResponseNoErrors(response)

       
