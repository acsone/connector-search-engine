# -*- coding: utf-8 -*-

import mock
from odoo import _
from odoo.exceptions import ValidationError
from odoo.addons.queue_job.tests.common import JobMixin

from .common import ConnectorElasticsearchCase
from .common import mock_api
from .models import ResPartner


class TestConnectorElasticsearch(ConnectorElasticsearchCase, JobMixin):
    def _init_test_model(self, model_cls):
        registry = self.env.registry
        cr = self.env.cr
        inst = model_cls._build_model(registry, cr)
        model = self.env[model_cls._name].with_context(todo=[])
        model._prepare_setup()
        model._setup_base(partial=False)
        model._setup_fields(partial=False)
        model._setup_complete()
        model._auto_init()
        model.init()
        model._auto_end()
        return inst

    def setUp(self):
        super(TestConnectorElasticsearch, self).setUp()
        ir_model_res_partner = self.env["ir.model"].search(
            [("model", "=", "res.partner")]
        )
        res_lang = self.env["res.lang"].search([], limit=1)
        self.exporter = self.env.ref("base_jsonify.ir_exp_partner")
        self.se_config = self.env["se.index.config"].create(
            {
                "name": "my_config",
                "doc_type": "odoo_doc",
                "body": {"mappings": {"odoo_doc": {}}},
            }
        )
        self.se_index_model = self.env["se.index"]
        self.se_index = self.se_index_model.create(
            {
                "backend_id": self.backend.se_backend_id.id,
                "model_id": ir_model_res_partner.id,
                "lang_id": res_lang.id,
                "exporter_id": self.exporter.id,
                "config_id": self.se_config.id,
            }
        )

        # init our test model after the creation of the index since this one
        # will be used as default value
        # we must mock the commit to be sure that odoo will not commit when
        # initializing the model
        self.cr.commit = mock.MagicMock()
        self._init_test_model(ResPartner)

    def test_recompute_all_indexes(self):
        partner = self.env.ref("base.main_partner")
        self.assertEqual(partner.data, {})

        jobs = self.job_counter()
        self.se_index_model.recompute_all_index(
            [("id", "=", self.se_index.id)]
        )

        # check that a job have been created for each binding
        nbr_binding = self.env["res.partner"].search_count([])
        self.assertEqual(jobs.count_created(), nbr_binding)
        self.perform_jobs(jobs)

        # check that all binding have been recomputed and set to be updated
        nbr_binding_to_update = self.env["res.partner"].search_count(
            [("sync_state", "=", "to_update")]
        )
        self.assertEqual(nbr_binding_to_update, nbr_binding)

        # Check that the json data have been updated
        parser = self.exporter.get_json_parser()
        data = partner.jsonify(parser)[0]
        data["id"] = partner.id  # the mapper add the id of the record
        self.assertDictEqual(partner.data, data)

    def test_export_jobs(self):
        # Set partner to be updated with fake vals in data
        partners = self.env["res.partner"].search([])
        partners.write(
            {"sync_state": "to_update", "data": {"objectID": "foo"}}
        )
        count = len(partners)

        # Generate Batch export job
        jobs = self.job_counter()
        self.se_index_model.generate_batch_export_per_index(
            [("id", "=", self.se_index.id)]
        )
        self.assertEqual(jobs.count_created(), 1)
        self.assertEqual(
            _("Prepare a batch export of index '%s'") % self.se_index.name,
            jobs.search_created().name,
        )
        # Run batch export and check that export job have been created
        jobs2 = self.job_counter()
        self.perform_jobs(jobs)
        self.assertEqual(jobs2.count_created(), 1)
        self.assertEqual(
            _(
                "Export %d records of %d for index "
                "'demo_elasticsearch_backend_partner_en_US'"
            )
            % (count, count),
            jobs2.search_created().name,
        )

        # Run export job and check that elasticsearch has been called
        with mock_api(self.env) as mocked_api:
            self.assertFalse(self.se_index.name.lower() in mocked_api.index)
            self.perform_jobs(jobs2)
            index_name = self.se_index.name.lower()
            self.assertIn(index_name, mocked_api.index)
            self.assertEqual(
                mocked_api.index[index_name].get("body"), self.se_config.body
            )

    def test_index_config(self):
        """Check constrains on doc_type and config body: If a mappings is
        specified, at least one entry must exist for the given doctype
        """
        self.assertEqual(self.se_config.doc_type, "odoo_doc")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.se_config.body = {"mappings": "toto"}
        self.se_config.write(
            {
                "doc_type": "new_doc_type",
                "body": {"mappings": {"new_doc_type": {}}},
            }
        )

    def test_inex_config_as_str(self):
        self.se_config.write(
            {"body_str": '{"mappings": {"odoo_doc": {"1":1}}}'}
        )
        self.assertDictEqual(
            self.se_config.body, {"mappings": {"odoo_doc": {"1": 1}}}
        )
