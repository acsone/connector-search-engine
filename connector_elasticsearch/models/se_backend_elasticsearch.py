# -*- coding: utf-8 -*-
# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SeBackendElasticsearch(models.Model):

    _name = "se.backend.elasticsearch"
    _inherit = "se.backend.spec.abstract"
    _description = "Elasticsearch Backend"

    elasticsearch_server_ip = fields.Char(
        sparse="data", string="ElasticSearch IP adress"
    )
    elasticsearch_server_port = fields.Char(
        sparse="data", string="ElasticSearch Port"
    )

    def init(self):
        # The init is called at install/update only before loading xml data
        # and demo data. Moreovoer these data are loaded before the end of
        # the initialization of the registry. Therefore we must also
        # register our backend to avoid error when loading the data since
        # the _register_hook is not yet called when the xml data are imported
        self.env["se.backend"].register_spec_backend(self)

    def _register_hook(self):
        # The register hook is called each time the registry is initialized,
        # not only at install.
        # Register our specialized backend
        self.env["se.backend"].register_spec_backend(self)
